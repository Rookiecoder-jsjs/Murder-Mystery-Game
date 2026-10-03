# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Tests for GameSession persistence, snapshots, and vote handling.

LLM calls are faked with a stub client — no network access.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

import pytest
from app.core.errors import GameError as HTTPException

from app.core.phases import GamePhase
from app.domain.models import PlayerState
from app.services.session_service import (
    GameSession,
    InMemorySessionStore,
    JsonFileSessionStore,
    SessionManager,
    _restore_state,
)
from tests.conftest import sample_archive  # noqa: F401  (fixture import)


class _FakeToolFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name: str, arguments: str):
        self.type = "function"
        self.function = _FakeToolFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content: str | None, tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: _FakeMessage):
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage):
        self.choices = [_FakeChoice(message)]


class StubRoleplayClient:
    """OpenAI-client stand-in returning canned replies.

    Voting prompts (which mention ``submit_vote``) yield a forced tool call
    to exercise the structured-vote path; everything else returns text.
    """

    def __init__(self, reply: str = "我觉得线索很有意思。"):
        self.reply = reply
        self.calls: list[dict] = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        texts = [m.get("content", "") for m in kwargs.get("messages", [])]
        if kwargs.get("tool_choice", {}).get("function", {}).get("name") == "check_statement":
            data = json.loads(texts[1])
            return _FakeResponse(_FakeMessage(None, [_FakeToolCall(
                "check_statement", json.dumps({"checks": [], "valid": True, "issues": [],
                    "segments": [{"segment_index": i, "supported": True, "non_factual": True,
                        "source_id": "", "quote": "", "unsupported_details": []}
                        for i, _ in enumerate(data["speech_segments"])]}),
            )]))
        if kwargs.get("tool_choice", {}).get("function", {}).get("name") == "submit_vote":
            tool_call = _FakeToolCall(
                "submit_vote",
                '{"target_id": "char_2", "brief_reason": "他的时间线对不上"}',
            )
            return _FakeResponse(_FakeMessage(content=None, tool_calls=[tool_call]))
        tool_call = _FakeToolCall("submit_statement", json.dumps({
            "speech": self.reply, "claims": [], "corrections": [],
        }, ensure_ascii=False))
        return _FakeResponse(_FakeMessage(content=None, tool_calls=[tool_call]))


@pytest.fixture
def manager(sample_archive):
    store = InMemorySessionStore()
    mgr = SessionManager(
        roleplay_client=StubRoleplayClient(),
        story_service=_FakeStoryService(sample_archive),
        store=store,
    )
    yield mgr


class _FakeStoryService:
    def __init__(self, archive):
        self._archive = archive

    def create_story(self, topic, show_reasoning=False):
        return self._archive

    def get_story(self, story_id):
        if story_id == self._archive.id:
            return self._archive
        return None

    get_playable_story = get_story


# ---------- snapshot round trip ----------


class TestSnapshotRoundTrip:
    def test_quick_mode_state_and_investigation_options(self, sample_archive):
        session = GameSession(
            sample_archive,
            "char_2",
            StubRoleplayClient(),
            mode="quick",
        )
        session.game.set_phase(GamePhase.INVESTIGATION)

        status = session.get_game_status()

        assert status["mode"] == "quick"
        assert status["max_rounds"] == 3
        assert [o["id"] for o in status["investigation_options"]] == ["clue_a"]

        result = session.investigate(status["investigation_options"][0]["id"])

        assert result["found"]
        assert result["event"]["title"]
        assert result["investigation_options"] == []
        session.game.state.round = 2
        assert session.get_investigation_options()

    def test_quick_mode_survives_snapshot_restore(self, sample_archive):
        session = GameSession(
            sample_archive,
            "char_2",
            StubRoleplayClient(),
            mode="quick",
        )
        snapshot = session.to_snapshot("g1")

        restored = GameSession.from_snapshot(
            snapshot, sample_archive, StubRoleplayClient()
        )

        assert restored.game.state.mode == "quick"
        assert restored.game.state.max_rounds == 3

    def test_restore_yields_typed_player_states(self, sample_archive):
        game_id = "g1"
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.state.round = 3
        session.game.state.discussion_history.append("Alice: 你好")
        snap = session.to_snapshot(game_id)

        restored = GameSession.from_snapshot(
            snap, sample_archive, StubRoleplayClient()
        )
        ps = restored.game.state.player_states["char_1"]
        assert isinstance(ps, PlayerState)
        assert ps.is_alive is True
        assert restored.game.state.round == 3
        assert restored.human_player_id == "char_2"

    def test_revealed_clues_survive_restart(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        # Flip a hidden clue to revealed, as investigation would
        target = next(
            c for c in sample_archive.clues if not c.reveal_to_all
        )
        target.reveal_to_all = True
        snap = session.to_snapshot("g1")

        fresh = GameSession.from_snapshot(
            snap, sample_archive, StubRoleplayClient()
        )
        by_id = {c.id: c for c in fresh.archive.clues}
        assert by_id[target.id].reveal_to_all is True


# ---------- persistence stores ----------


class TestJsonFileStore:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = JsonFileSessionStore(str(tmp_path / "sessions"))
        snapshot = {"game_id": "abc", "state": {"phase": "voting"}}
        store.save(snapshot)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["game_id"] == "abc"

    def test_delete_removes_file(self, tmp_path):
        store = JsonFileSessionStore(str(tmp_path / "sessions"))
        store.save({"game_id": "abc"})
        store.delete("abc")
        assert store.load_all() == []

    def test_corrupt_file_skipped(self, tmp_path):
        d = tmp_path / "sessions"
        d.mkdir()
        (d / "bad.json").write_text("{not json", encoding="utf-8")
        store = JsonFileSessionStore(str(d))
        assert store.load_all() == []


# ---------- manager persistence wiring ----------


class TestManagerPersistence:
    def test_save_uses_game_id_key(self, manager, sample_archive):
        game_id, session = manager.create_session(archive=sample_archive)
        # mutate state after creation, then save under game_id
        session.game.state.phase = "discussion"
        manager.save(game_id)  # must NOT raise even without file store

    def test_load_all_persisted_restores_sessions(self, tmp_path, sample_archive):
        store = JsonFileSessionStore(str(tmp_path / "s"))
        mgr1 = SessionManager(
            roleplay_client=StubRoleplayClient(),
            story_service=_FakeStoryService(sample_archive),
            store=store,
        )
        game_id, session = mgr1.create_session(archive=sample_archive)
        session.game.next_phase()
        mgr1.save(game_id)

        mgr2 = SessionManager(
            roleplay_client=StubRoleplayClient(),
            story_service=_FakeStoryService(sample_archive),
            store=store,
        )
        count = mgr2.load_all_persisted()
        assert count == 1
        restored = mgr2.get(game_id)
        assert isinstance(
            restored.game.state.player_states["char_1"], PlayerState
        )

    def test_load_skips_missing_story(self, tmp_path, sample_archive):
        store = JsonFileSessionStore(str(tmp_path / "s"))
        mgr1 = SessionManager(
            roleplay_client=StubRoleplayClient(),
            story_service=_FakeStoryService(sample_archive),
            store=store,
        )
        game_id, _ = mgr1.create_session(archive=sample_archive)

        class _EmptyService(_FakeStoryService):
            def get_story(self, story_id):
                return None

        mgr2 = SessionManager(
            roleplay_client=StubRoleplayClient(),
            story_service=_EmptyService(sample_archive),
            store=store,
        )
        assert mgr2.load_all_persisted() == 0


# ---------- restore helper ----------


class TestRestoreState:
    def test_defaults_for_missing_fields(self, sample_archive):
        raw = {"story_id": sample_archive.id}
        state = _restore_state(raw, sample_archive)
        assert state.phase == "introduction"
        assert set(state.player_states.keys()) == {
            c.id for c in sample_archive.characters
        }

    def test_restore_derives_max_rounds_from_mode(self, sample_archive):
        """坏快照可能连 max_rounds 一起写坏——恢复时按规范化后的
        mode 重新推导，与 GameManager.__init__ 保持一致。"""
        raw = {"story_id": sample_archive.id, "mode": "garbage", "max_rounds": 3}
        state = _restore_state(raw, sample_archive)
        assert state.mode == "classic"
        assert state.max_rounds == 5

        raw_quick = {
            "story_id": sample_archive.id, "mode": "quick", "max_rounds": 99,
        }
        assert _restore_state(raw_quick, sample_archive).max_rounds == 3


# ---------- vote fallback (deadlock guard) ----------


class TestVoteFallback:
    """A failing/unparseable AI vote must not stall the whole round."""

    def _voting_session(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.set_phase(GamePhase.VOTING)
        return session

    def test_failing_ai_abstains_without_blocking_verdict(self, sample_archive):
        session = self._voting_session(sample_archive)
        session.ai_characters["char_3"].get_vote = lambda **kw: ("", "")
        result = asyncio.run(session.vote_async("Alice"))
        advice = asyncio.run(session.collect_ballot_advice())
        assert next(b for b in advice["votes"] if b["voter"] == "Carol")["target"] == "弃权"
        assert result["game_ended"] and result["winner"] == "good"
        assert result["all_submitted"] is True
        restored = GameSession.from_snapshot(session.to_snapshot("g"), sample_archive, StubRoleplayClient())
        assert any(v["voter"] == "Carol" and v["target"] == "弃权"
                   for v in restored.get_reveal_info()["votes"])

    def test_ai_exception_does_not_change_player_result(self, sample_archive):
        session = self._voting_session(sample_archive)
        def fail(**kwargs):
            raise RuntimeError("模拟模型失败")
        session.ai_characters["char_3"].get_vote = fail
        result = asyncio.run(session.vote_async("Dave"))
        advice = asyncio.run(session.collect_ballot_advice())
        assert next(b for b in advice["votes"] if b["voter"] == "Carol")["target"] == "弃权"
        assert result["game_ended"] and result["winner"] == "killer"

    def test_stalled_optional_advice_cannot_delay_or_overwrite_verdict(self, sample_archive, monkeypatch):
        from app.services import session_service
        session = self._voting_session(sample_archive)
        result = asyncio.run(session.vote_async("Alice"))
        monkeypatch.setattr(session_service, "NPC_VOTE_TIMEOUT_SECONDS", 0.01)
        async def saved():
            pass
        monkeypatch.setattr(session, "_save_background", saved)
        async def run():
            loop = asyncio.get_running_loop()
            monkeypatch.setattr(loop, "run_in_executor", lambda *args: loop.create_future())
            return await asyncio.wait_for(session.collect_ballot_advice(), timeout=1)
        advice = asyncio.run(run())
        assert result["game_ended"] and result["winner"] == "good"
        assert advice["winner"] == "good"
        assert all(b["target"] == "弃权" for b in advice["votes"] if b["voter"] != "Bob")
        assert not session.is_speaking

    def test_dead_target_is_rejected_before_ai_calls(self, sample_archive):
        client = StubRoleplayClient()
        session = GameSession(sample_archive, "char_2", client)
        session.game.set_phase(GamePhase.VOTING)
        session.game.eliminate_player("char_3")
        with pytest.raises(HTTPException):
            asyncio.run(session.vote_async("Carol"))
        assert not client.calls
        assert not session.game.state.votes_record


# ---------- vote function calling (structured output) ----------


class TestVoteTool:
    def test_tool_target_and_reason_recorded(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.set_phase(GamePhase.VOTING)

        asyncio.run(session.vote_async("Alice"))

        asyncio.run(session.collect_ballot_advice())
        advice = {b["voter"]: b for b in session.get_reveal_info()["votes"]}
        assert advice["Dave"]["target"] == "Bob"
        assert advice["Dave"]["reason"] == "他的时间线对不上"
        assert len(session.game.state.votes_record) == 1
        assert len(advice) == 4


# ---------- snapshot defensive copy ----------


class TestSnapshotDefensiveCopy:
    def test_event_snapshot_is_not_alias(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.add_discussion("char_3", "已发言")
        snap = session.to_snapshot("g1")
        assert "ai_memories" not in snap
        session.game.add_discussion("char_2", "新发言")
        assert len(snap["state"]["discussion_events"]) == 1
        assert snap["state"]["discussion_events"][0]["text"] == "已发言"


# ---------- quick-mode phase guards ----------


class TestQuickModeInvestigation:
    def _session(self, sample_archive):
        session = GameSession(
            sample_archive, "char_2", StubRoleplayClient(), mode="quick",
        )
        return session

    def test_options_available_in_discussion(self, sample_archive):
        """讨论阶段 available_actions 会明示 investigate——
        options 列表必须同步支持，否则按钮点了必 400。"""
        session = self._session(sample_archive)
        session.game.set_phase(GamePhase.DISCUSSION)

        assert session.get_investigation_options()

    def test_investigate_during_discussion(self, sample_archive):
        session = self._session(sample_archive)
        session.game.set_phase(GamePhase.DISCUSSION)
        options = session.get_investigation_options()

        result = session.investigate(options[0]["id"])

        assert result["found"]
        assert result["event"]["title"]

    def test_investigate_with_empty_pool_reports_exhausted(self, sample_archive):
        session = self._session(sample_archive)
        session.game.set_phase(GamePhase.INVESTIGATION)
        for clue_id in ("clue_a", "clue_b", "clue_c", "clue_d"):
            session.game.distribute_clue("char_2", clue_id)
        session.game.distribute_clue("char_2", "clue_locked")  # 解锁后一并拿走
        assert session.get_investigation_options() == []

        with pytest.raises(HTTPException) as exc:
            session.investigate()

        assert "已经没有更多线索" in exc.value.detail

    def test_restore_state_normalizes_invalid_mode(self, sample_archive):
        raw = {"story_id": sample_archive.id, "mode": "garbage"}

        state = _restore_state(raw, sample_archive)

        assert state.mode == "classic"
        assert state.max_rounds == 5

    def test_last_event_cleared_on_phase_change(self, sample_archive):
        """突发事件横幅只跟随触发它的搜证，进入下一阶段后不再滞留。"""
        session = self._session(sample_archive)
        session.game.set_phase(GamePhase.INVESTIGATION)
        options = session.get_investigation_options()
        session.investigate(options[0]["id"])
        assert session.game.state.last_event is not None

        session.game.set_phase(GamePhase.DISCUSSION)

        assert session.game.state.last_event is None

    def test_status_actions_match_callable_endpoints(self, sample_archive):
        """available_actions 必须与真实可调用的端点一致：
        round < max 可搜证/可返回搜证但不可进投票；
        round == max 仍可补查，完成调查与讨论后才可投票。"""
        session = self._session(sample_archive)
        session.game.set_phase(GamePhase.DISCUSSION)

        status = session.get_game_status()
        assert "investigate" in status["available_actions"]
        assert "return_investigation" in status["available_actions"]
        assert "vote" not in status["available_actions"]

        session.game.state.round = session.game.state.max_rounds
        status = session.get_game_status()
        assert "investigate" in status["available_actions"]
        assert "return_investigation" in status["available_actions"]
        assert "vote" not in status["available_actions"]
        session.investigate()
        asyncio.run(session.player_speak_collect("最终推论"))
        assert "vote" in session.get_game_status()["available_actions"]


# ---------- case brief (public synopsis, spoiler-free) ----------


class TestCaseBrief:
    """案情简报只下发公开字段，动机与真凶是谜底，绝不进常规载荷。"""

    def test_status_brief_has_public_fields_only(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())

        brief = session.get_game_status()["case_brief"]

        assert brief["title"] == "测试案件"
        assert brief["background"] == "案件背景"
        assert brief["victim"] == "受害者"
        assert brief["crime"] == "受害者被害"
        assert "motive" not in brief
        assert "true_killer" not in brief

    def test_reveal_still_carries_truth(self, sample_archive):
        """谜底仍走 reveal 通道（对照：简报裁剪不影响揭晓完整性）。"""
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())

        session.game.force_reveal()
        reveal = session.get_reveal_info()

        assert reveal["case_info"]["motive"] == "动机"
        assert reveal["case_info"]["true_killer"] == "char_1"


class TestReviewRegressions:
    def test_human_is_always_an_innocent(self, sample_archive, monkeypatch):
        choices = []
        def choose(ids):
            choices.extend(ids)
            return ids[0]
        monkeypatch.setattr("app.services.session_service.random.choice", choose)
        manager = SessionManager(StubRoleplayClient(), None)
        game_id, session = manager.create_session(archive=sample_archive)
        assert "char_1" not in choices
        assert session.human_player_id != session.game.killer_id
        assert session.get_game_status()["game_id"] == game_id
        restored = GameSession.from_snapshot(session.to_snapshot(game_id), sample_archive, StubRoleplayClient())
        assert restored.get_game_status()["game_id"] == game_id

    def test_introductions_are_idempotent(self, sample_archive):
        client = StubRoleplayClient()
        session = GameSession(sample_archive, "char_2", client)
        first = asyncio.run(session.player_introduce_async("初次介绍"))
        count = len(client.calls)
        second = asyncio.run(session.player_introduce_async("重试介绍"))
        assert second == first
        assert len(client.calls) == count
        assert len(session.get_discussion_history()) == len(sample_archive.characters)

    def test_disconnect_finishes_and_persists_all_replies(self, sample_archive):
        import threading
        from app.api.endpoints.games import speak_stream
        from app.api.schemas import SpeakRequest
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.set_phase(GamePhase.DISCUSSION)
        gate = threading.Event()
        snapshots = []
        session.set_persistence_callback(lambda: snapshots.append(session.to_snapshot("demo")))
        for index, ai in enumerate(session.ai_characters.values()):
            def respond(ai=ai, index=index, **kwargs):
                if index:
                    assert gate.wait(5)
                reply = f"回复{index}"
                return reply
            ai.respond = respond

        async def run():
            stream = await speak_stream("demo", SpeakRequest(message="提问"), session, None)
            try:
                accepted = await anext(stream.body_iterator)
                assert '"kind": "question"' in accepted
                assert session.discussion_task is not None
                with pytest.raises(HTTPException):
                    session.accuse("Alice")
                await stream.body_iterator.aclose()
            finally:
                gate.set()
            await asyncio.wait_for(asyncio.shield(session.discussion_task), 5)
        asyncio.run(run())
        assert len(session.get_discussion_history()) == 4
        assert "ai_memories" not in snapshots[-1]
        assert len(snapshots[-1]["state"]["discussion_events"]) == 4
        assert len(snapshots[-1]["state"]["discussion_history"]) == 4
        assert not session.get_game_status()["is_speaking"]


def test_legacy_reveal_snapshot_remains_readable(sample_archive):
    session = GameSession(sample_archive, "char_2", StubRoleplayClient())
    snapshot = session.to_snapshot("legacy-game")
    snapshot["state"]["phase"] = "reveal"
    snapshot["state"]["game_ended"] = False
    snapshot["state"].pop("investigated_round")
    snapshot["state"].pop("discussed_round")
    restored = GameSession.from_snapshot(snapshot, sample_archive, StubRoleplayClient())
    assert restored.get_game_status()["game_ended"] is True
    assert restored.get_reveal_info()["case_info"]["true_killer"] == "char_1"
    assert restored.game.state.investigated_round == 0
