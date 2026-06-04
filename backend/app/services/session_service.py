# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game session lifecycle and business logic.

Owns:
- ``GameSession`` — per-game state, AI character roster, and game actions
- ``SessionManager`` — in-memory registry of sessions with pluggable
  persistence (``InMemorySessionStore`` default; ``JsonFileSessionStore``
  restores games after process restart)

The HTTP layer (``app.api.endpoints.*``) is a thin shell that maps
requests to methods on these classes — no game logic should live in
endpoint handlers.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import asdict
from typing import Any, AsyncIterable, Dict, Optional, Protocol

from fastapi import HTTPException
from openai import OpenAI

from app.agents.m2_character import M2Character
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.domain.game_manager import GameManager
from app.domain.models import GameState, StoryArchive


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Persistence protocol
# ---------------------------------------------------------------------------


class SessionStore(Protocol):
    """Minimal contract for session persistence backends."""

    def save(self, snapshot: Dict[str, Any]) -> None: ...
    def load_all(self) -> list[Dict[str, Any]]: ...
    def delete(self, game_id: str) -> None: ...


class InMemorySessionStore:
    """No-op store — sessions are lost on process exit."""

    def save(self, snapshot: Dict[str, Any]) -> None:
        return None

    def load_all(self) -> list[Dict[str, Any]]:
        return []

    def delete(self, game_id: str) -> None:
        return None


class JsonFileSessionStore:
    """Persist each session as a JSON file under a directory."""

    def __init__(self, directory: str) -> None:
        self._dir = directory
        os.makedirs(self._dir, exist_ok=True)

    def _path(self, game_id: str) -> str:
        return os.path.join(self._dir, f"{game_id}.json")

    def save(self, snapshot: Dict[str, Any]) -> None:
        path = self._path(snapshot["game_id"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

    def load_all(self) -> list[Dict[str, Any]]:
        if not os.path.isdir(self._dir):
            return []
        results: list[Dict[str, Any]] = []
        for name in os.listdir(self._dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception as e:
                logger.warning("Skipping corrupt session file %s: %s", path, e)
        return results

    def delete(self, game_id: str) -> None:
        path = self._path(game_id)
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# GameSession — single game's runtime
# ---------------------------------------------------------------------------


class GameSession:
    """Runtime state and actions for one murder mystery game."""

    def __init__(
        self,
        archive: StoryArchive,
        human_player_id: str,
        m2_client: OpenAI,
    ) -> None:
        self.archive = archive
        self.game = GameManager(archive)
        self.human_player_id = human_player_id
        self.m2_client = m2_client
        self.m2_config = get_config().minimax

        self.ai_characters: Dict[str, M2Character] = {}
        for char in archive.characters:
            if char.id != human_player_id:
                self.ai_characters[char.id] = M2Character(
                    character=char,
                    client=m2_client,
                    config=self.m2_config,
                )

        self._distribute_initial_clues()

    def _distribute_initial_clues(self) -> None:
        self.game.distribute_random_clues(self.human_player_id, 1)
        for char_id in self.ai_characters:
            board = self.game.get_clue_board(char_id)
            if board.available:
                self.game.distribute_random_clues(char_id, 1)

    def to_snapshot(self, game_id: str) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot of mutable state.

        AI conversation history is NOT persisted — the next request will
        rebuild it from the discussion log on demand.
        """
        return {
            "game_id": game_id,
            "story_id": self.archive.id,
            "human_player_id": self.human_player_id,
            "state": asdict(self.game.state),
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Dict[str, Any],
        archive: StoryArchive,
        m2_client: OpenAI,
    ) -> "GameSession":
        """Reconstruct a session from a snapshot and its archive."""
        session = cls.__new__(cls)
        session.archive = archive
        session.game = GameManager(archive)
        session.human_player_id = snapshot["human_player_id"]
        session.m2_client = m2_client
        session.m2_config = get_config().minimax

        session.game.state = GameState(**snapshot["state"])

        session.ai_characters = {}
        for char in archive.characters:
            if char.id != session.human_player_id:
                session.ai_characters[char.id] = M2Character(
                    character=char,
                    client=m2_client,
                    config=session.m2_config,
                )
        return session

    # -- read-only views -----------------------------------------------------

    def get_player_info(self) -> Dict[str, Any]:
        char = self.game.get_character(self.human_player_id)
        return {
            "id": char.id,
            "name": char.name,
            "public_identity": char.public_identity,
            "appearance": char.appearance,
        }

    def get_all_characters(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "public_identity": c.public_identity,
                "appearance": c.appearance,
            }
            for c in self.archive.characters
        ]

    def get_clue_board(self) -> Dict[str, Any]:
        board = self.game.get_clue_board(self.human_player_id)

        def clue_to_info(entry):
            holder_name = "场景"
            if entry.clue.holder_id != "scene":
                holder = self.game.get_character(entry.clue.holder_id)
                if holder:
                    holder_name = holder.name
            return {
                "id": entry.clue.id,
                "content": entry.clue.content,
                "type": entry.clue.type,
                "holder_name": holder_name,
                "is_revealed": entry.status == "scene_public",
            }

        clues = [clue_to_info(e) for e in board.owned]
        scene_public = [clue_to_info(e) for e in board.scene_public]
        human_state = self.game.state.player_states[self.human_player_id]
        return {
            "clues": clues,
            "accusation_points": human_state.accusation_points,
            "scene_public_clues": scene_public,
        }

    def get_game_status(self) -> Dict[str, Any]:
        actions = []
        phase = self.game.state.phase
        if phase == "introduction":
            actions = ["introduce"]
        elif phase == "investigation":
            actions = ["view_clues", "discuss", "accuse"]
        elif phase == "discussion":
            actions = ["speak", "view_clues", "accuse", "vote", "return_investigation"]
        elif phase == "voting":
            actions = ["vote"]
        elif phase == "reveal":
            actions = []
        return {
            "game_id": self.archive.id,
            "phase": phase,
            "round": self.game.state.round,
            "max_rounds": self.game.state.max_rounds,
            "player": self.get_player_info(),
            "characters": self.get_all_characters(),
            "available_actions": actions,
        }

    def get_reveal_info(self) -> Dict[str, Any]:
        return {
            "story_content": self.archive.story_content,
            "winner": self.game.state.winner or "unknown",
            "case_info": {
                "title": self.archive.case.title,
                "background": self.archive.case.background,
                "victim": self.archive.case.victim,
                "crime": self.archive.case.crime,
                "motive": self.archive.case.motive,
                "true_killer": self.game.killer_id,
            },
        }

    # -- actions -------------------------------------------------------------

    def player_introduce(self, message: str = "") -> Dict[str, Any]:
        human_char = self.game.get_character(self.human_player_id)
        ai_introductions = []
        for ai in self.ai_characters.values():
            response = ai.respond_introduction()
            ai_introductions.append({"speaker": ai.name, "message": response})
        self.game.next_phase()
        return {
            "player_introduction": message or f"大家好，我是{human_char.name}，{human_char.public_identity}。",
            "ai_introductions": ai_introductions,
            "new_phase": self.game.state.phase,
        }

    def accuse(self, character_name: str) -> Dict[str, Any]:
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")
        if not self.game.can_accuse(self.human_player_id):
            raise HTTPException(status_code=400, detail="已经没有指认次数了")
        correct, message = self.game.accuse(self.human_player_id, target_id)
        return {
            "correct": correct,
            "message": message,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
        }

    async def player_speak_async(
        self, message: str
    ) -> AsyncIterable[Dict[str, Any]]:
        """Async variant of ``player_speak`` that yields each response as
        soon as that AI character finishes — multiple AIs run concurrently.

        Yields dicts in the same shape as ``player_speak``'s return list:
        ``{"speaker": <name>, "message": <text>}``. The first yielded item
        is always the human player's message; AI responses follow in
        completion order, not character order.
        """
        import asyncio

        human_char = self.game.get_character(self.human_player_id)
        self.game.add_discussion(self.human_player_id, message)
        yield {"speaker": human_char.name, "message": message}

        loop = asyncio.get_running_loop()

        async def _respond(char_id: str, ai: "M2Character"):
            ai_state = self.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                return None
            known = self.game.get_player_clues(char_id)
            response = await loop.run_in_executor(
                None,
                lambda: ai.respond(
                    user_input=message,
                    phase=GamePhase.DISCUSSION,
                    known_clues=known,
                    revealed_clues=self.game.get_revealed_clues(),
                    other_chars=[
                        c for c in self.archive.characters if c.id != char_id
                    ],
                    discussion_history=self.game.state.discussion_history,
                ),
            )
            return (ai.name, response)

        tasks = [
            asyncio.create_task(_respond(cid, ai))
            for cid, ai in self.ai_characters.items()
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result is None:
                continue
            name, response = result
            self.game.add_discussion(self._char_id_for(name), response)
            yield {"speaker": name, "message": response}

    def _char_id_for(self, name: str) -> str:
        """Resolve a character name to id (helper)."""
        for c in self.archive.characters:
            if c.name == name:
                return c.id
        return name

    def player_speak(self, message: str) -> list[Dict[str, Any]]:
        """Sync wrapper — runs all AI responses in parallel threads.

        The blocking OpenAI calls are dispatched to a thread pool so
        multiple characters' responses overlap. Result is a flat list
        in the same shape as the original sequential implementation.
        """
        import asyncio

        async def _collect():
            return [m async for m in self.player_speak_async(message)]

        return asyncio.run(_collect())

    def vote(self, character_name: str) -> Dict[str, Any]:
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")
        self.game.submit_vote(self.human_player_id, target_id)
        for char_id, ai in self.ai_characters.items():
            ai_state = self.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                continue
            ai_vote = ai.get_vote()
            if ai_vote in self.game.alive_players:
                self.game.submit_vote(char_id, ai_vote)
        _, result = self.game.check_voting_result()
        return {
            "votes": {},
            "result": result,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
        }


# ---------------------------------------------------------------------------
# SessionManager — registry + persistence wiring
# ---------------------------------------------------------------------------


class SessionManager:
    """Owns the registry of active sessions and persistence policy."""

    def __init__(
        self,
        m2_client: OpenAI,
        story_service,
        store: Optional[SessionStore] = None,
    ) -> None:
        self._m2_client = m2_client
        self._story_service = story_service
        self._store = store or InMemorySessionStore()
        self._sessions: Dict[str, GameSession] = {}

    def create_session(
        self,
        topic: Optional[str] = None,
        archive: Optional[StoryArchive] = None,
    ) -> tuple[str, GameSession]:
        """Create a new game session.

        Exactly one of ``topic`` or ``archive`` must be provided.
        """
        if (topic is None) == (archive is None):
            raise ValueError("Provide exactly one of topic or archive")
        if topic is not None:
            archive = self._story_service.create_story(topic, show_reasoning=True)
            if not archive:
                raise RuntimeError("生成案件失败")

        char_ids = [c.id for c in archive.characters]
        human_id = random.choice(char_ids)
        session = GameSession(archive, human_id, self._m2_client)
        game_id = str(uuid.uuid4())
        self._sessions[game_id] = session
        self._store.save(session.to_snapshot(game_id))
        logger.info("Created session %s for story %s", game_id, archive.id)
        return game_id, session

    def get(self, game_id: str) -> GameSession:
        session = self._sessions.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="游戏不存在")
        return session

    def save(self, game_id: str) -> None:
        session = self._sessions.get(game_id)
        if session is None:
            return
        self._store.save(session.to_snapshot(game_id))

    def load_all_persisted(self) -> int:
        """Restore all sessions from the store into memory.

        Sessions whose underlying story archive is missing are skipped.
        """
        count = 0
        for snap in self._store.load_all():
            game_id = snap.get("game_id")
            if not game_id or game_id in self._sessions:
                continue
            archive = self._story_service.get_story(snap["story_id"])
            if not archive:
                logger.warning(
                    "Skipping session %s — story %s not found",
                    game_id, snap["story_id"],
                )
                continue
            self._sessions[game_id] = GameSession.from_snapshot(
                snap, archive, self._m2_client,
            )
            count += 1
        if count:
            logger.info("Restored %d session(s) from disk", count)
        return count

    def list_active(self) -> list[str]:
        return list(self._sessions.keys())
