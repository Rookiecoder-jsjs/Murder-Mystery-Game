# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game session lifecycle and business logic.

Owns:
- ``GameSession`` — per-game state, AI character roster, and game actions
- ``SessionManager`` — in-memory registry of sessions with pluggable
  persistence (``InMemorySessionStore`` default; ``JsonFileSessionStore``
  restores games after process restart)

All LLM calls are async (thread-pool offload) so the FastAPI event loop
is never blocked. The HTTP layer (``app.api.endpoints.*``) is a thin
shell that maps requests to methods on these classes — no game logic
should live in endpoint handlers.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from dataclasses import asdict
from typing import Any, AsyncIterable, Dict, List, Optional, Protocol

from fastapi import HTTPException
from openai import OpenAI

from app.agents.roleplay_character import RoleplayCharacter
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.domain.game_manager import GameManager
from app.domain.models import GameState, PlayerState, StoryArchive


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


def _restore_state(raw: Dict[str, Any], archive: StoryArchive) -> GameState:
    """Rebuild a typed ``GameState`` from a JSON snapshot.

    ``asdict`` flattens nested dataclasses to dicts; restore them here so
    callers can rely on real ``PlayerState`` objects after a restart.
    """
    state = GameState(
        story_id=raw["story_id"],
        phase=raw.get("phase", "introduction"),
        turn=raw.get("turn", 0),
        round=raw.get("round", 1),
        max_rounds=raw.get("max_rounds", 5),
        investigation_count=raw.get("investigation_count", 0),
        min_investigation_rounds=raw.get("min_investigation_rounds", 2),
        eliminated_id=raw.get("eliminated_id"),
        votes_record=list(raw.get("votes_record", [])),
        discussion_history=list(raw.get("discussion_history", [])),
        game_ended=raw.get("game_ended", False),
        winner=raw.get("winner"),
        reveal_triggered=raw.get("reveal_triggered", False),
    )
    for char in archive.characters:
        ps_raw = raw.get("player_states", {}).get(char.id)
        if isinstance(ps_raw, dict):
            state.player_states[char.id] = PlayerState(
                character_id=char.id,
                is_alive=ps_raw.get("is_alive", True),
                accusation_points=ps_raw.get("accusation_points", 1),
                known_clues=list(ps_raw.get("known_clues", [])),
                has_accused=ps_raw.get("has_accused", False),
                vote=ps_raw.get("vote"),
            )
        else:
            state.player_states[char.id] = PlayerState(character_id=char.id)
    return state


# ---------------------------------------------------------------------------
# GameSession — single game's runtime
# ---------------------------------------------------------------------------


class GameSession:
    """Runtime state and actions for one murder mystery game."""

    def __init__(
        self,
        archive: StoryArchive,
        human_player_id: str,
        roleplay_client: OpenAI,
    ) -> None:
        self.archive = archive
        self.game = GameManager(archive)
        self.human_player_id = human_player_id
        self.roleplay_client = roleplay_client
        self.roleplay_config = get_config().roleplay

        human_char = self.game.get_character(human_player_id)
        persona = (
            f"{human_char.name}（{human_char.public_identity}）"
            if human_char else ""
        )

        self.ai_characters: Dict[str, RoleplayCharacter] = {}
        for char in archive.characters:
            if char.id != human_player_id:
                self.ai_characters[char.id] = RoleplayCharacter(
                    character=char,
                    client=roleplay_client,
                    user_persona=persona,
                    case=self.archive.case,
                    config=self.roleplay_config,
                )

        self._distribute_initial_clues()

    def _distribute_initial_clues(self) -> None:
        self.game.distribute_random_clues(self.human_player_id, 1)
        for char_id in self.ai_characters:
            board = self.game.get_clue_board(char_id)
            if board.available:
                self.game.distribute_random_clues(char_id, 1)

    # -- persistence ---------------------------------------------------------

    def to_snapshot(self, game_id: str) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot of mutable state.

        Includes scene-clue reveal flags (they mutate the archive at
        runtime) so a restored game sees the same clue board.
        """
        return {
            "game_id": game_id,
            "story_id": self.archive.id,
            "human_player_id": self.human_player_id,
            "state": asdict(self.game.state),
            "revealed_clue_ids": [
                c.id for c in self.archive.clues if c.reveal_to_all
            ],
            # AI 角色的私有对话记忆 —— 不落盘则重启后所有角色失忆
            "ai_memories": {
                cid: ai.conversation_history
                for cid, ai in self.ai_characters.items()
            },
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Dict[str, Any],
        archive: StoryArchive,
        roleplay_client: OpenAI,
    ) -> "GameSession":
        """Reconstruct a session from a snapshot and its archive."""
        session = cls.__new__(cls)
        session.archive = archive
        session.game = GameManager(archive)
        session.human_player_id = snapshot["human_player_id"]
        session.roleplay_client = roleplay_client
        session.roleplay_config = get_config().roleplay

        revealed_ids = set(snapshot.get("revealed_clue_ids", []))
        for clue in archive.clues:
            clue.reveal_to_all = clue.id in revealed_ids or clue.reveal_to_all

        session.game.state = _restore_state(snapshot["state"], archive)

        human_char = session.game.get_character(session.human_player_id)
        persona = (
            f"{human_char.name}（{human_char.public_identity}）"
            if human_char else ""
        )

        ai_memories = snapshot.get("ai_memories", {})
        session.ai_characters = {}
        for char in archive.characters:
            if char.id != session.human_player_id:
                ai = RoleplayCharacter(
                    character=char,
                    client=roleplay_client,
                    user_persona=persona,
                    case=session.archive.case,
                    config=session.roleplay_config,
                )
                ai.conversation_history = ai_memories.get(char.id, [])
                session.ai_characters[char.id] = ai
        return session

    # -- read-only views -----------------------------------------------------

    def _char_name(self, char_id: str) -> str:
        """Resolve a character ID to its name (falls back to the ID)."""
        char = self.game.get_character(char_id)
        return char.name if char else char_id

    def get_player_info(self) -> Dict[str, Any]:
        char = self.game.get_character(self.human_player_id)
        return {
            "id": char.id,
            "name": char.name,
            "public_identity": char.public_identity,
            "appearance": char.appearance,
        }

    def get_all_characters(self, include_private: bool = False) -> List[Dict[str, Any]]:
        """List characters.

        Args:
            include_private: Include killer/motive fields. Only safe in
                the reveal payload — never expose during play.
        """
        result = []
        for c in self.archive.characters:
            info = {
                "id": c.id,
                "name": c.name,
                "public_identity": c.public_identity,
                "appearance": c.appearance,
            }
            if include_private:
                info.update({
                    "is_killer": c.is_killer,
                    "motive": c.motive,
                    "backstory": c.backstory,
                    "relationship_with_victim": c.relationship_with_victim,
                })
            result.append(info)
        return result

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
            actions = ["view_clues", "investigate", "discuss", "accuse"]
        elif phase == "discussion":
            actions = ["speak", "view_clues", "investigate", "accuse", "vote", "return_investigation"]
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
            "investigation_count": self.game.state.investigation_count,
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
                "true_killer_name": self._char_name(self.game.killer_id),
            },
            "characters": self.get_all_characters(include_private=True),
        }

    def get_discussion_history(self) -> List[Dict[str, str]]:
        """Parse the shared discussion log into speaker/message pairs."""
        messages = []
        for line in self.game.state.discussion_history:
            speaker, _, message = line.partition(": ")
            messages.append({"speaker": speaker, "message": message})
        return messages

    # -- context assembly ----------------------------------------------------

    def _ai_context(self, char_id: str) -> Dict[str, Any]:
        """Assemble the live game context for one AI character."""
        return {
            "known_clues": self.game.get_player_clues(char_id),
            "revealed_clues": self.game.get_revealed_clues(),
            "other_chars": list(self.archive.characters),
            "discussion_history": self.game.state.discussion_history,
            "case": self.archive.case,
        }

    # -- actions -------------------------------------------------------------

    async def player_introduce_async(self, message: str = "") -> Dict[str, Any]:
        """Collect introductions: all AI characters respond concurrently."""
        human_char = self.game.get_character(self.human_player_id)
        player_intro = message or (
            f"大家好，我是{human_char.name}，{human_char.public_identity}。"
        )

        loop = asyncio.get_running_loop()

        async def _intro(ai: RoleplayCharacter):
            return await loop.run_in_executor(None, ai.respond_introduction)

        responses = await asyncio.gather(*(
            _intro(ai) for ai in self.ai_characters.values()
        ))

        ai_introductions = []
        for ai, response in zip(self.ai_characters.values(), responses):
            ai_introductions.append({"speaker": ai.name, "message": response})
            self.game.add_discussion(ai.character_id, response)
        self.game.add_discussion(self.human_player_id, player_intro)

        # Do NOT auto-advance the phase — the frontend shows the
        # introductions and explicitly moves to investigation.
        return {
            "player_introduction": player_intro,
            "ai_introductions": ai_introductions,
            "new_phase": self.game.state.phase,
        }

    def investigate(self) -> Dict[str, Any]:
        """Active investigation: draw one new clue for the player.

        Usable in the investigation phase and mid-discussion; errors out
        when nothing remains to find.
        """
        if self.game.current_phase not in (
            GamePhase.INVESTIGATION, GamePhase.DISCUSSION,
        ):
            raise HTTPException(status_code=400, detail="当前阶段不能搜证")

        found = self.game.distribute_random_clues(self.human_player_id, 1)
        if not found:
            raise HTTPException(status_code=400, detail="已经没有更多线索了")
        return {
            "found": [
                {
                    "id": c.id,
                    "content": c.content,
                    "type": c.type,
                    "holder_name": self._char_name(c.holder_id),
                }
                for c in found
            ],
            "clue_board": self.get_clue_board(),
        }

    def accuse(self, character_name: str) -> Dict[str, Any]:
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")
        correct, message = self.game.accuse(self.human_player_id, target_id)
        if not correct and "不能" in message:
            # domain rejected the target itself (self/dead) — surface as 400
            raise HTTPException(status_code=400, detail=message)
        return {
            "correct": correct,
            "message": message,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
        }

    async def player_speak_async(
        self, message: str
    ) -> AsyncIterable[Dict[str, Any]]:
        """Yield each AI response as soon as that character finishes —
        multiple AIs run concurrently via thread-pool offload.

        Yields dicts shaped ``{"speaker": <name>, "message": <text>}``.
        The caller is responsible for echoing the human player's own
        message (the frontend already shows it optimistically).
        """
        self.game.add_discussion(self.human_player_id, message)

        loop = asyncio.get_running_loop()

        async def _respond(char_id: str, ai: RoleplayCharacter):
            ai_state = self.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                return None
            ctx = self._ai_context(char_id)
            response = await loop.run_in_executor(
                None,
                lambda: ai.respond(
                    user_input=message,
                    phase=self.game.current_phase,
                    **ctx,
                ),
            )
            return (char_id, ai.name, response)

        tasks = [
            asyncio.create_task(_respond(cid, ai))
            for cid, ai in self.ai_characters.items()
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result is None:
                continue
            char_id, name, response = result
            self.game.add_discussion(char_id, response)
            yield {"speaker": name, "message": response}

    async def player_speak_collect(self, message: str) -> List[Dict[str, Any]]:
        """Batch variant of ``player_speak_async`` for non-streaming
        endpoints — awaits every AI response into one list."""
        return [m async for m in self.player_speak_async(message)]

    async def vote_async(self, character_name: str) -> Dict[str, Any]:
        """Submit the player's vote and collect AI votes concurrently.

        Votes are cleared at round start, each player's vote replaces
        their previous one, and AI replies are parsed by name or ID.
        """
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")
        if not target_id or not self.game.can_vote(self.human_player_id):
            raise HTTPException(status_code=400, detail="当前无法投票")

        self.game.submit_vote(self.human_player_id, target_id)

        loop = asyncio.get_running_loop()
        alive_ai_ids = [
            cid for cid in self.ai_characters
            if (self.game.state.player_states.get(cid) or PlayerState("")).is_alive
        ]

        async def _vote(char_id: str, ai: RoleplayCharacter):
            ctx = self._ai_context(char_id)
            raw = await loop.run_in_executor(
                None, lambda: ai.get_vote(**ctx),
            )
            return (char_id, ai.name, raw)

        results = await asyncio.gather(*(
            _vote(cid, ai) for cid, ai in self.ai_characters.items() if cid in alive_ai_ids
        ))

        votes_view: Dict[str, str] = {}
        for char_id, name, raw in results:
            parsed = RoleplayCharacter.parse_vote_target(raw, list(self.archive.characters))
            if parsed in self.game.alive_players and parsed != char_id:
                self.game.submit_vote(char_id, parsed)
            if parsed:
                votes_view[name] = self._char_name(parsed)

        ended, result_msg = self.game.check_voting_result()
        return {
            "votes": votes_view,
            "result": result_msg,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
            "phase": self.game.state.phase,
            "all_submitted": len(self.game.get_votes()) >= len(self.game.alive_players),
        }


# ---------------------------------------------------------------------------
# SessionManager — registry + persistence wiring
# ---------------------------------------------------------------------------


class SessionManager:
    """Owns the registry of active sessions and persistence policy."""

    def __init__(
        self,
        roleplay_client: OpenAI,
        story_service,
        store: Optional[SessionStore] = None,
    ) -> None:
        self._roleplay_client = roleplay_client
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
        session = GameSession(archive, human_id, self._roleplay_client)
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
            try:
                self._sessions[game_id] = GameSession.from_snapshot(
                    snap, archive, self._roleplay_client,
                )
            except Exception as e:
                logger.warning("Skipping corrupt session %s: %s", game_id, e)
                continue
            count += 1
        if count:
            logger.info("Restored %d session(s) from disk", count)
        return count

    def list_active(self) -> list[str]:
        return list(self._sessions.keys())
