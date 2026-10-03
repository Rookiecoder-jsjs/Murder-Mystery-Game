# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Tests for RoleplayCharacter.get_vote structured (tool-call) voting.

No network access — the OpenAI client is faked.
"""

from __future__ import annotations

import json

from app.agents.roleplay_character import RoleplayCharacter
from app.core.config import RoleplayConfig
from app.domain.models import CaseData, ScriptCharacter


def _char(id: str, name: str, is_killer: bool = False) -> ScriptCharacter:
    return ScriptCharacter(
        id=id,
        name=name,
        public_identity=f"{name}的公开身份",
        secret=f"{name}的秘密",
        is_killer=is_killer,
        alibi=f"{name}的不在场证明",
        dialogue_style="冷静",
        backstory=f"{name}的背景故事",
        relationship_with_victim=f"{name}与受害者的关系",
        appearance=f"{name}的外貌",
    )


class _ToolFunction:
    def __init__(self, arguments: str, name: str = "submit_vote"):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, arguments: str, name: str = "submit_vote"):
        self.type = "function"
        self.function = _ToolFunction(arguments, name)


class _Message:
    def __init__(self, content: str | None = None, tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message: _Message):
        self.message = message


class _Response:
    def __init__(self, message: _Message):
        self.choices = [_Choice(message)]


class FakeClient:
    """Returns a canned chat completion for every request."""

    def __init__(self, message: _Message):
        self._message = message
        self.last_kwargs: dict = {}

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if kwargs.get("tool_choice", {}).get("function", {}).get("name") == "check_statement":
            return _Response(_Message(tool_calls=[_ToolCall('{"checks":[],"segments":[],"valid":true,"issues":[]}', "check_statement")]))
        return _Response(self._message)


def _character_role(client) -> RoleplayCharacter:
    killer = _char("char_1", "Alice", is_killer=True)
    case = CaseData(
        title="测试案件",
        background="1930年代上海",
        victim="受害者",
        crime="受害者被害",
        true_killer="char_1",
        motive="动机",
    )
    return RoleplayCharacter(
        character=killer,
        client=client,
        user_persona="Bob（Bob的公开身份）",
        case=case,
        config=RoleplayConfig(api_key="test", base_url="http://localhost"),
    )


OTHER_CHARS = [
    _char("char_2", "Bob"),
    _char("char_3", "Carol"),
    _char("char_4", "Dave"),
]


def _vote_kwargs(client: FakeClient) -> dict:
    """The kwargs of the last create() call, asserted for tool wiring."""
    return client.last_kwargs


def test_tool_call_yields_target_and_reason():
    client = FakeClient(
        _Message(tool_calls=[_ToolCall(
            '{"target_id": "char_2", "brief_reason": "他的时间线对不上"}'
        )])
    )
    role = _character_role(client)

    target, reason = role.get_vote(other_chars=OTHER_CHARS)

    assert target == "char_2"
    assert reason == "他的时间线对不上"


def test_tool_is_forced_and_context_pins_candidates():
    client = FakeClient(_Message(tool_calls=[_ToolCall('{"target_id": "char_2"}')]))
    role = _character_role(client)

    role.get_vote(other_chars=OTHER_CHARS)

    kwargs = _vote_kwargs(client)
    assert kwargs["tool_choice"] == {
        "type": "function", "function": {"name": "submit_vote"},
    }
    # Dynamic allowlists must not rewrite tool definitions or include self.
    target_schema = kwargs["tools"][0]["function"]["parameters"]["properties"]["target_id"]
    assert "enum" not in target_schema
    assert json.loads(kwargs["messages"][1]["content"])["candidates"] == ["char_2", "char_3", "char_4"]


def test_text_reply_falls_back_to_name_parse():
    client = FakeClient(_Message(content="我投 Bob，他就是凶手。"))
    role = _character_role(client)

    target, reason = role.get_vote(other_chars=OTHER_CHARS)

    assert target == "char_2"
    assert reason == ""


def test_text_reply_falls_back_to_char_id_parse():
    client = FakeClient(_Message(content="我认为 char_3 最可疑"))
    role = _character_role(client)

    target, reason = role.get_vote(other_chars=OTHER_CHARS)

    assert target == "char_3"
    assert reason == ""


def test_malformed_tool_args_and_no_content_yields_empty():
    client = FakeClient(_Message(tool_calls=[_ToolCall("not-json")]))
    role = _character_role(client)

    assert role.get_vote(other_chars=OTHER_CHARS) == ("", "")


def test_no_tool_no_content_yields_empty():
    client = FakeClient(_Message(content=None))
    role = _character_role(client)

    assert role.get_vote(other_chars=OTHER_CHARS) == ("", "")


def test_innocent_prompt_uses_personal_knowledge_and_can_admit_evidence():
    from app.core.phases import GamePhase
    char = _char('char_2', 'Bob')
    char.secret = '全知作者写明 Alice 下毒'
    char.backstory = '全知作者背景'
    char.self_knowledge = '我隐瞒了欠债，案发时在大厅。'
    client = FakeClient(_Message(content='证据既然证明，我承认欠债。'))
    role = RoleplayCharacter(char, client)
    role.respond('解释证据', GamePhase.DISCUSSION)
    prompt = '\n'.join(m['content'] for m in client.last_kwargs['messages'])
    assert char.self_knowledge in prompt
    assert '必须承认相关经历' in prompt
    assert '全知作者' not in prompt
    previous_call = client.last_kwargs
    introduction = role.respond_introduction()
    assert char.self_knowledge not in introduction
    assert char.public_identity in introduction
    assert client.last_kwargs is previous_call  # No invented introduction biography.


class SequenceClient(FakeClient):
    def __init__(self, messages):
        self.messages = iter(messages)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(next(self.messages))


def statement(speech, claims=None, corrections=None):
    return _Message(tool_calls=[_ToolCall(json.dumps({
        "speech": speech, "claims": claims or [], "corrections": corrections or [],
    }, ensure_ascii=False), "submit_statement")])


def review(valid=True, issues=None, *, vote=False):
    return _Message(tool_calls=[_ToolCall(json.dumps({
        "checks": [], "valid": valid, "issues": issues or [],
        "segments": [] if vote else [{"segment_index": 0, "supported": True,
            "non_factual": True, "source_id": "", "quote": "", "unsupported_details": []}],
    }), "check_statement")])


def test_invalid_clock_claim_retries_without_remembering_bad_draft():
    from app.core.phases import GamePhase
    invented = "我在十九时给死者注射药物。"
    client = SequenceClient([
        statement(invented, [{"text": invented, "kind": "observed", "source_ids": ["self:knowledge"]}]),
        statement("具体时间我无法确认。"), review(),
    ])
    role = _character_role(client)
    assert role.respond("什么时候？", GamePhase.DISCUSSION) == "具体时间我无法确认。"
    assert len(client.calls) == 3
    assert invented not in str(role.conversation_history)
    repair = json.loads(client.calls[1]["messages"][-1]["content"])
    assert invented in repair['rejected_draft']
    assert '不是事实或历史' in repair['task']
    assert invented not in str(client.calls[1]["messages"][:3])


def test_semantic_review_rejects_invented_movement_before_publication():
    from app.core.phases import GamePhase
    speech = "我后来把药瓶从木匣挪进了抽屉。"
    client = SequenceClient([
        statement(speech, [{"text": speech, "kind": "observed", "source_ids": ["self:knowledge"]}]),
        review(False, ["本人知识未记载移动药瓶的经历"]),
        statement("我无法确认药瓶曾被移动。"), review(),
    ])
    role = _character_role(client)
    role.character.self_knowledge = "药瓶放在抽屉。"
    assert role.respond("为什么之前说在木匣？", GamePhase.DISCUSSION) == "我无法确认药瓶曾被移动。"
    assert len(client.calls) == 4
    assert speech not in str(role.conversation_history)
    assert client.calls[1]["tool_choice"]["function"]["name"] == "check_statement"


def test_two_invalid_outputs_produce_safe_clarification():
    from app.core.phases import GamePhase
    client = SequenceClient([_Message(content="不合法的原始回答"), _Message(content="还是不合法")])
    role = _character_role(client)
    response = role.respond("解释一下", GamePhase.DISCUSSION)
    assert "无法确认" in response
    assert len(client.calls) == 2
    assert "不合法" not in str(role.conversation_history)


def test_structured_vote_outside_candidates_is_rejected():
    role = _character_role(FakeClient(_Message(tool_calls=[_ToolCall('{"target_id":"char_1"}')])))
    assert role.get_vote(other_chars=OTHER_CHARS) == ("", "")


def test_reviewer_cannot_certify_an_invented_source_quote():
    import pytest
    from app.core.phases import GamePhase
    from app.core.roleplay_protocol import InvalidStatement
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps({
        "valid": True, "issues": [], "checks": [{
            "claim_index": 0, "supported": True, "source_id": "self:knowledge",
            "quote": "我把药瓶从木匣挪进抽屉。",
        }],
        "segments": [{"segment_index": 0, "supported": True, "non_factual": False,
                      "source_id": "self:knowledge", "quote": "我把药瓶从木匣挪进抽屉。", "unsupported_details": []}],
    }), "check_statement")])])
    role = _character_role(client)
    role.character.self_knowledge = "我随身带了药片。"
    context = role._legacy_context("药瓶在哪里？", GamePhase.DISCUSSION, role.case, [], [], [],
                                   ["Alice: 之前编造的木匣经历"])
    raw = json.dumps({"speech": "我把药瓶挪了。", "claims": [{
        "text": "我把药瓶挪了。", "kind": "observed", "source_ids": ["self:knowledge"],
    }], "corrections": []})
    with pytest.raises(InvalidStatement, match="真实原文"):
        role._review_statement(raw, context, 1)
    sent = json.loads(client.calls[0]["messages"][1]["content"])
    assert sent["reports"] == []
    assert "之前编造的木匣经历" not in json.dumps(sent, ensure_ascii=False)
    assert client.calls[0]["temperature"] == 0
