"""Cache-friendly requests must preserve role permissions and actual telemetry."""

from dataclasses import replace
import json

import pytest

from app.core.phases import GamePhase
from app.core.prompt_cache import cache_usage, prefix_fingerprint, summarize_cache
from app.core.roleplay_protocol import statement_tool_spec, vote_tool_spec
from app.services.context_service import ContextAssembler, encode, estimate_tokens
from app.services.session_service import GameSession
from tests.test_context_service import session_for
from tests.test_session_service import StubRoleplayClient
from tests.test_roleplay_character import SequenceClient, review


def messages(session, context, question="问题"):
    return session.ai_characters[context.character_id]._build_messages(
        question, GamePhase(context.phase), context=context,
    )


def test_phase_round_and_action_changes_preserve_fixed_prefix(sample_archive):
    session = session_for(sample_archive)
    first = session._ai_context("char_3", action_id="first", user_input="第一问")["context"]
    session.game.state.round += 1
    session.game.set_phase(GamePhase.INVESTIGATION)
    second = session._ai_context("char_3", action_id="second", user_input="下一问")["context"]
    assert first.stable_prefix == second.stable_prefix
    assert first.payload_json.split(',"phase":')[0] == second.payload_json.split(',"phase":')[0]
    assert messages(session, first)[0] == messages(session, second)[0]
    assert second.payload()["round"] != first.payload()["round"]
    assert second.payload()["phase"] == "investigation"
    assert "first" not in first.payload_json


def test_ninth_event_appends_without_rewriting_old_quotes(sample_archive):
    session = session_for(sample_archive)
    for n in range(8):
        session.game.add_discussion("char_3", f"已经说过的第{n}句话")
    first = session._ai_context("char_3")["context"]
    session.game.add_discussion("char_4", "第九句")
    second = session._ai_context("char_3")["context"]
    assert not first.omitted_event_ids and not second.omitted_event_ids
    assert second.payload()["testimony"][:8] == first.payload()["testimony"]
    # Strip only the old array terminator; all earlier request bytes survive.
    assert second.payload_json.startswith(first.payload_json.split('],"phase":')[0])
    assert second.payload()["allowed_correction_ids"] == [f"e{i}" for i in range(1, 9)]
    assert "event:e9" in second.payload()["allowed_source_ids"]
    assert "e9" not in second.payload()["allowed_correction_ids"]


def test_publication_changes_status_at_tail_not_evidence_body(sample_archive):
    session = session_for(sample_archive)
    first = session._ai_context("char_3")["context"]
    session.game.present_clues("char_3", ["clue_c"])
    second = session._ai_context("char_3")["context"]
    assert first.payload()["clues"] == second.payload()["clues"]
    assert first.payload_json.split(',"public_clue_ids":')[0] == second.payload_json.split(',"public_clue_ids":')[0]
    assert "clue_c" not in first.payload()["public_clue_ids"]
    assert "clue_c" in second.payload()["public_clue_ids"]


def test_input_order_and_save_restore_produce_identical_requests(sample_archive):
    kwargs = dict(character=sample_archive.characters[2], phase=GamePhase.DISCUSSION,
                  case=sample_archive.case, known_clues=sample_archive.clues[:2],
                  revealed_clues=sample_archive.clues[1:3], other_chars=sample_archive.characters)
    first = ContextAssembler.assemble(**kwargs)
    shuffled = ContextAssembler.assemble(**(kwargs | {
        "known_clues": list(reversed(kwargs["known_clues"])),
        "revealed_clues": list(reversed(kwargs["revealed_clues"])),
        "other_chars": list(reversed(kwargs["other_chars"])),
    }))
    assert first.payload_json == shuffled.payload_json
    session = session_for(sample_archive)
    session.game.add_discussion("char_3", "保存前已说过")
    first = session._ai_context("char_3")["context"]
    restored = GameSession.from_snapshot(json.loads(json.dumps(session.to_snapshot("restored"))),
                                         sample_archive, StubRoleplayClient())
    second = restored._ai_context("char_3")["context"]
    assert first.stable_prefix == second.stable_prefix
    assert messages(session, first) == messages(restored, second)


def test_each_role_has_own_fixed_prefix_and_permission_changes_are_fresh(sample_archive):
    sample_archive.characters[2].self_knowledge = "CAROL_PRIVATE"
    sample_archive.characters[3].self_knowledge = "DAVE_PRIVATE"
    session = session_for(sample_archive)
    carol = session._ai_context("char_3")["context"]
    dave = session._ai_context("char_4")["context"]
    assert carol.stable_prefix != dave.stable_prefix
    assert "DAVE_PRIVATE" not in carol.payload_json
    assert "CAROL_PRIVATE" not in dave.payload_json
    # Role data edits invalidate the prefix; no stale local prompt cache exists.
    sample_archive.characters[2].self_knowledge = "CAROL_CHANGED"
    changed = session._ai_context("char_3")["context"]
    assert changed.stable_prefix != carol.stable_prefix
    assert "CAROL_PRIVATE" not in changed.payload_json
    session.game.set_phase(GamePhase.INTRODUCTION)
    intro = session._ai_context("char_3")["context"]
    assert "CAROL_CHANGED" not in str(messages(session, intro))
    assert "self:knowledge" not in intro.payload()["allowed_source_ids"]


def test_source_revocation_never_reuses_private_data(sample_archive):
    kwargs = dict(character=sample_archive.characters[2], phase=GamePhase.DISCUSSION,
                  case=sample_archive.case, known_clues=[sample_archive.clues[2]])
    first = ContextAssembler.assemble(**kwargs)
    revoked = ContextAssembler.assemble(**(kwargs | {"known_clues": []}))
    assert first.stable_prefix == revoked.stable_prefix  # Only fixed facts are reusable.
    assert "clue:clue_c" not in revoked.payload_json
    assert "clue:clue_c" not in {s.source_id for s in revoked.sources}


@pytest.mark.parametrize("phase", [GamePhase.DISCUSSION, GamePhase.VOTING])
def test_estimate_measures_actual_serialized_request(sample_archive, phase):
    session = session_for(sample_archive)
    session.game.set_phase(phase)
    context = session._ai_context("char_3", user_input="当前问题")["context"]
    tools = [vote_tool_spec()] if phase == GamePhase.VOTING else [statement_tool_spec()]
    actual = {"messages": messages(session, context, "当前问题"), "tools": tools}
    assert context.estimated_tokens == estimate_tokens(encode(actual)) + 1024
    assert context.payload_json.startswith(context.stable_prefix)
    assert set(context.payload()["allowed_source_ids"]) == {s.source_id for s in context.sources}


def test_tool_schema_and_prefix_survive_new_sources(sample_archive, monkeypatch):
    from app.agents import roleplay_character
    from tests.test_roleplay_character import statement
    session = session_for(sample_archive)
    role = session.ai_characters["char_3"]
    role.client = SequenceClient([statement("无法确认。"), review(), statement("还需核对。"), review()])
    traces = []
    monkeypatch.setattr(roleplay_character, "trace_llm_chat", lambda **kw: traces.append(kw))
    first = session._ai_context("char_3")["context"]
    role.respond("问题一", GamePhase.DISCUSSION, context=first)
    session.game.add_discussion("char_4", "可见的新证言")
    second = session._ai_context("char_3")["context"]
    role.respond("问题二", GamePhase.DISCUSSION, context=second)
    assert role.client.calls[0]["tools"] == role.client.calls[2]["tools"]
    assert traces[0]["context"]["cache_prefix_sha256"] == traces[2]["context"]["cache_prefix_sha256"]
    assert traces[1]["context"]["cache_prefix_sha256"] == traces[3]["context"]["cache_prefix_sha256"]
    assert traces[0]["context"]["cache_prefix_sha256"] != traces[1]["context"]["cache_prefix_sha256"]
    assert "可见的新证言" not in str(role.client.calls[3]["messages"])


def test_validator_keeps_fact_prefix_when_draft_and_review_mode_change(sample_archive):
    session = session_for(sample_archive)
    context = session._ai_context("char_3")["context"]
    role = session.ai_characters["char_3"]
    role.client = SequenceClient([review(), review(vote=True)])
    role._review_statement(encode({"speech": "无法确认。", "claims": [], "corrections": []}), context, 1)
    role._review_statement(encode({"speech": "我还需核对。", "claims": [], "corrections": []}),
                           replace(context, phase="voting"), 1)
    a, b = [call["messages"] for call in role.client.calls]
    assert a[0] == b[0]
    assert a[1]["content"].split(',"reports":')[0] == b[1]["content"].split(',"reports":')[0]
    assert json.loads(a[1]["content"])["mode"] == "statement"
    assert json.loads(b[1]["content"])["mode"] == "vote"


@pytest.mark.parametrize("raw, expected", [
    ({"prompt_tokens": 100, "prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 20}, (100, 80, 20, .8)),
    ({"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 0}}, (100, 0, 100, 0)),
    ({"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 75}}, (100, 75, 25, .75)),
    ({"prompt_tokens": 100}, (100, None, None, None)),
    ({"prompt_tokens": 100, "prompt_cache_hit_tokens": 101}, (100, None, None, None)),
    ({"prompt_tokens": 100, "prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 50}, (100, None, None, None)),
    (None, (None, None, None, None)),
])
def test_cache_usage_reports_actual_tokens_or_unknown(raw, expected):
    assert tuple(cache_usage(raw).values()) == expected


def test_aggregation_is_weighted_and_separates_roles_stages_and_unknown():
    def record(char, stage, prompt, hit=None):
        return {"kind": "roleplay", "model": "m", "context": {"character_id": char, "stage": stage},
                "usage": {"prompt_tokens": prompt, "prompt_cache_hit_tokens": hit}}
    rows = summarize_cache([
        record("a", "generation", 100, 100), record("a", "generation", 300, 0),
        record("a", "generation", 999), record("a", "validation", 100, 50),
        record("b", "generation", 100, 30),
    ])
    assert len(rows) == 3
    assert rows[0]["hit_rate"] == .25  # Not average(100%, 0%) or missing-as-zero.
    assert rows[0]["reported_calls"] == 2
    assert rows[0]["unknown_calls"] == 1
    assert rows[1]["hit_rate"] == .5
    assert rows[2]["hit_rate"] == .3


def test_fingerprint_includes_model_and_tool_configuration():
    kwargs = dict(model="a", system="rules", context_prefix="private", tools=[statement_tool_spec()],
                  tool_choice={"name": "submit_statement"}, thinking=False)
    first = prefix_fingerprint(**kwargs)
    assert first == prefix_fingerprint(**kwargs)
    for changes in ({"model": "b"}, {"thinking": True}, {"tools": [vote_tool_spec()]}, {"context_prefix": "changed"}):
        assert first != prefix_fingerprint(**(kwargs | changes))
