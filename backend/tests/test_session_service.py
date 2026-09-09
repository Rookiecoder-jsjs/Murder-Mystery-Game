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
        if any("submit_vote" in (t or "") for t in texts):
            tool_call = _FakeToolCall(
                "submit_vote",
                '{"target_id": "char_2", "brief_reason": "他的时间线对不上"}',
            )
            return _FakeResponse(_FakeMessage(content=None, tool_calls=[tool_call]))
        return _FakeResponse(_FakeMessage(content=self.reply))


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
        assert len(status["investigation_options"]) == 2

        result = session.investigate(status["investigation_options"][0]["id"])

        assert result["found"]
        assert result["event"]["title"]
        assert result["investigation_options"]

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


# ---------- vote fallback (deadlock guard) ----------


class TestVoteFallback:
    """A failing/unparseable AI vote must not stall the whole round."""

    def _voting_session(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.set_phase(GamePhase.VOTING)
        return session

    def test_failing_ai_still_gets_a_vote(self, sample_archive):
        session = self._voting_session(sample_archive)
        # char_3 (Carol) always fails to produce a usable vote.
        session.ai_characters["char_3"].get_vote = lambda **kw: ("", "")

        result = asyncio.run(session.vote_async("Alice"))

        # Every alive player (human + 3 AIs) must have cast a vote; otherwise
        # check_voting_result never opens the ballot ("等待投票中..." forever).
        assert len(session.game.state.votes_record) == 4
        assert result["all_submitted"] is True
        assert "等待投票中" not in result["result"]

    def test_fallback_target_is_alive_and_not_self(self, sample_archive):
        session = self._voting_session(sample_archive)
        session.ai_characters["char_3"].get_vote = lambda **kw: ("", "")

        alive_before = set(session.game.alive_players)
        asyncio.run(session.vote_async("Alice"))

        entry = next(
            v for v in session.game.state.votes_record
            if v["player_id"] == "char_3"
        )
        assert entry["target_id"] in alive_before
        assert entry["target_id"] != "char_3"


# ---------- vote function calling (structured output) ----------


class TestVoteTool:
    def test_tool_target_and_reason_recorded(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.game.set_phase(GamePhase.VOTING)

        asyncio.run(session.vote_async("Alice"))

        by_player = {v["player_id"]: v for v in session.game.state.votes_record}
        # char_4 is an AI whose stub always returns the submit_vote tool call.
        assert by_player["char_4"]["target_id"] == "char_2"
        assert by_player["char_4"].get("reason") == "他的时间线对不上"
        # Every alive player voted (human + 3 AIs).
        assert len(session.game.state.votes_record) == 4


# ---------- snapshot defensive copy ----------


class TestSnapshotDefensiveCopy:
    def test_ai_memory_snapshot_is_not_alias(self, sample_archive):
        session = GameSession(sample_archive, "char_2", StubRoleplayClient())
        session.ai_characters["char_3"].conversation_history.append(
            {"role": "assistant", "message": "已发言"}
        )

        snap = session.to_snapshot("g1")
        assert snap["ai_memories"]["char_3"] == [
            {"role": "assistant", "message": "已发言"}
        ]

        # Appending after snapshotting must not retroactively change it.
        session.ai_characters["char_3"].conversation_history.append(
            {"role": "user", "message": "新发言"}
        )
        assert snap["ai_memories"]["char_3"] == [
            {"role": "assistant", "message": "已发言"}
        ]
