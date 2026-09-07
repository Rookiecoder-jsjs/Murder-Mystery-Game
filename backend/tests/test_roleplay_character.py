# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Tests for RoleplayCharacter.get_vote structured (tool-call) voting.

No network access — the OpenAI client is faked.
"""

from __future__ import annotations

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
    def __init__(self, arguments: str):
        self.name = "submit_vote"
        self.arguments = arguments


class _ToolCall:
    def __init__(self, arguments: str):
        self.type = "function"
        self.function = _ToolFunction(arguments)


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


def test_tool_is_forced_and_enum_pins_candidates():
    client = FakeClient(_Message(tool_calls=[_ToolCall('{"target_id": "char_2"}')]))
    role = _character_role(client)

    role.get_vote(other_chars=OTHER_CHARS)

    kwargs = _vote_kwargs(client)
    assert kwargs["tool_choice"] == {
        "type": "function", "function": {"name": "submit_vote"},
    }
    # enum must match the alive others (never the voter itself)
    enum = kwargs["tools"][0]["function"]["parameters"]["properties"]["target_id"]["enum"]
    assert enum == ["char_2", "char_3", "char_4"]


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
