# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Tests for GameSession persistence, snapshots, and vote handling.

LLM calls are faked with a stub client — no network access.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from app.domain.models import PlayerState
from app.services.session_service import (
    GameSession,
    InMemorySessionStore,
    JsonFileSessionStore,
    SessionManager,
    _restore_state,
)
from tests.conftest import sample_archive  # noqa: F401  (fixture import)


class _StubMessage:
    def __init__(self, content: str):
        self.content = content


class _StubChoice:
    def __init__(self, content: str):
        self.message = _StubMessage(content)


class _StubResponse:
    def __init__(self, content: str):
        self.choices = [_StubChoice(content)]


class StubRoleplayClient:
    """OpenAI-client stand-in returning canned replies."""

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
        # Voting prompts ask for char_X; reply with a name to exercise
        # the name-parsing path.
        system = kwargs.get("messages", [{}])[0].get("content", "")
        if "投票" in system or "char_" in system:
            return _StubResponse("我投 Bob，他就是凶手。")
        return _StubResponse(self.reply)


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
