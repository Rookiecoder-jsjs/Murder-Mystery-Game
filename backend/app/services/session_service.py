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
import tempfile
import threading
import time
import uuid
from dataclasses import asdict
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, Protocol

from typing import TYPE_CHECKING
from app.core.errors import GameError, ModelInterrupted
from app.core.runtime import is_embedded
if TYPE_CHECKING:
    from openai import OpenAI

from app.agents.roleplay_character import RoleplayCharacter
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.domain.game_manager import (
    GameManager,
    max_rounds_for_mode,
    normalize_mode,
)
from app.domain.models import GameState, PlayerState, StoryArchive
from app.domain.context import DiscussionEvent, RoleContext
from app.services.context_service import ContextAssembler, ContextBudgetExceeded


logger = get_logger(__name__)

# Advisory ballots must not hold the player's verdict behind a stalled model.
NPC_VOTE_TIMEOUT_SECONDS = 30.0


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
        # Background replies and HTTP teardown may save simultaneously.
        # Publish a complete file so readers never see a truncated JSON.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._dir,
                                             suffix=".tmp", delete=False) as f:
                temporary = f.name
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.remove(temporary)

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
    # 与 GameManager.__init__ 共用同一规范化：坏快照不得让恢复后的
    # 游戏静默偏离创建时的模式；max_rounds 也按规范化后的 mode 重新
    # 推导，被一并写坏的上限会自愈
    mode = normalize_mode(raw.get("mode", "classic"))
    state = GameState(
        story_id=raw["story_id"],
        mode=mode,
        phase=raw.get("phase", "introduction"),
        turn=raw.get("turn", 0),
        round=raw.get("round", 1),
        max_rounds=max_rounds_for_mode(mode),
        investigation_count=raw.get("investigation_count", 0),
        investigated_round=raw.get("investigated_round", 0),
        discussed_round=raw.get("discussed_round", 0),
        min_investigation_rounds=raw.get("min_investigation_rounds", 2),
        eliminated_id=raw.get("eliminated_id"),
        votes_record=list(raw.get("votes_record", [])),
        ballot_details=list(raw.get("ballot_details", [])),
        discussion_history=list(raw.get("discussion_history", [])),
        discussion_events=[DiscussionEvent.from_dict(e) for e in raw.get("discussion_events", [])],
        game_ended=raw.get("game_ended", False) or raw.get("phase") == "reveal",
        winner=raw.get("winner"),
        reveal_triggered=raw.get("reveal_triggered", False),
        last_event=raw.get("last_event"),
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
        mode: str = "classic",
        game_id: Optional[str] = None,
    ) -> None:
        self.game_id = game_id or str(uuid.uuid4())
        self._init_runtime()
        self.archive = archive
        self.game = GameManager(archive, mode=mode)
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

    def _init_runtime(self) -> None:
        self.discussion_task: Optional[asyncio.Task] = None
        self.pending_discussion: Optional[dict] = None
        self.pending_ballots: Optional[dict] = None
        self.last_activity = time.time()
        self._busy = False
        self._persistence_lock = asyncio.Lock()
        self._persist: Callable[[], None] = lambda: None

    def set_persistence_callback(self, callback: Callable[[], None]) -> None:
        """Bind the registry's snapshot writer to background discussion work."""
        self._persist = callback

    async def _save_background(self) -> None:
        try:
            async with self._persistence_lock:
                if is_embedded():
                    self._persist()  # Short SQLite commit on the engine thread, never the UI thread.
                else:
                    await asyncio.to_thread(self._persist)
        except Exception as exc:
            logger.warning("保存后台讨论失败: %s", exc)

    @property
    def is_speaking(self) -> bool:
        return self.discussion_task is not None and not self.discussion_task.done()

    def ensure_playable(self) -> None:
        """Reject mutations after the verdict or during another AI action."""
        if self.game.state.game_ended or self.game.current_phase == GamePhase.REVEAL:
            raise GameError(status_code=400, detail="游戏已经结束")
        if self._busy or self.is_speaking:
            raise GameError(status_code=409, detail="角色正在回应，请稍后再操作")
        if self.pending_discussion:
            raise GameError(status_code=409, detail="上一轮讨论未完成，请先继续该任务")

    def _investigated_this_round(self) -> bool:
        return (
            self.game.state.investigated_round == self.game.state.round
            or not self.game.get_available_clues(self.human_player_id)
        )

    def _completed_this_round(self) -> bool:
        return (
            self._investigated_this_round()
            and self.game.state.discussed_round == self.game.state.round
        )

    def phase_payload(self) -> Dict[str, Any]:
        status = self.get_game_status()
        return {key: status[key] for key in (
            "phase", "round", "investigation_options", "last_event", "available_actions", "round_progress",
        )}

    def advance_phase(self) -> Dict[str, Any]:
        """Advance only playable stages; votes exclusively decide the verdict."""
        self.ensure_playable()
        phase = self.game.current_phase
        if phase == GamePhase.VOTING:
            raise GameError(status_code=400, detail="请先完成投票")
        if self.game.state.mode == "quick":
            if phase == GamePhase.DISCUSSION:
                raise GameError(status_code=400, detail="速推模式请使用「下一轮调查」或「进入投票」推进")
            if phase == GamePhase.INVESTIGATION and not self._investigated_this_round():
                raise GameError(status_code=400, detail="请先调查一条线索，再进入讨论")
        if phase == GamePhase.DISCUSSION and self.game.state.round < self.game.state.max_rounds:
            self.game.state.round += 1
        else:
            self.game.next_phase()
        return self.phase_payload()

    def return_to_investigation(self) -> Dict[str, Any]:
        """Return for supplemental investigation without advancing quick rounds."""
        self.ensure_playable()
        phase = self.game.current_phase
        if phase not in (GamePhase.DISCUSSION, GamePhase.VOTING):
            raise GameError(status_code=400, detail="只能在讨论或投票阶段返回搜证")
        was_revote = phase == GamePhase.VOTING
        quick = self.game.state.mode == "quick"
        self.game.set_phase(GamePhase.INVESTIGATION)
        if was_revote:
            self.game.reset_votes()
        if not quick:
            self.game.distribute_random_clues(self.human_player_id, 1)
        for char_id in self.ai_characters:
            self.game.grant_role_clues(char_id)
        return self.phase_payload()

    def start_next_round(self) -> Dict[str, Any]:
        """Open the next quick investigation round after completed play."""
        self.ensure_playable()
        try:
            self.game.start_next_investigation_round(self.human_player_id)
        except ValueError as exc:
            raise GameError(400, str(exc)) from exc
        for char_id in self.ai_characters:
            self.game.grant_role_clues(char_id)
        return self.phase_payload()

    def start_voting(self) -> Dict[str, Any]:
        self.ensure_playable()
        if self.game.current_phase != GamePhase.DISCUSSION:
            raise GameError(status_code=400, detail="当前不是讨论阶段")
        if self.game.state.mode == "quick":
            if self.game.state.round < self.game.state.max_rounds:
                raise GameError(status_code=400, detail="请完成三轮调查和讨论后再进入投票")
            if not self._completed_this_round():
                raise GameError(status_code=400, detail="请先完成本轮调查并发表推论，再进入投票")
        self.game.set_phase(GamePhase.VOTING)
        self.game.reset_votes()
        return self.phase_payload()

    def _distribute_initial_clues(self) -> None:
        """Personal clue ownership follows the script, never a random draw."""
        for char in self.archive.characters:
            self.game.grant_role_clues(char.id)

    # -- persistence ---------------------------------------------------------

    def to_snapshot(self, game_id: str) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot of mutable state.

        Includes scene-clue reveal flags (they mutate the archive at
        runtime) so a restored game sees the same clue board.
        """
        self.game.migrate_discussion_history()
        return {
            "schema_version": 3,
            "game_id": game_id,
            "story_id": self.archive.id,
            "human_player_id": self.human_player_id,
            "pending_discussion": self.pending_discussion,
            "pending_ballots": self.pending_ballots,
            "last_activity": self.last_activity,
            "mode": self.game.state.mode,
            "state": asdict(self.game.state),
            "revealed_clue_ids": [
                c.id for c in self.archive.clues if c.reveal_to_all
            ],
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
        session.game_id = snapshot["game_id"]
        session._init_runtime()
        session.pending_discussion = snapshot.get('pending_discussion')
        session.pending_ballots = snapshot.get('pending_ballots')
        session.last_activity = snapshot.get('last_activity', 0)
        session.archive = archive
        snapshot_state = snapshot.get("state", {})
        mode = snapshot.get("mode", snapshot_state.get("mode", "classic"))
        session.game = GameManager(archive, mode=mode)
        session.human_player_id = snapshot["human_player_id"]
        session.roleplay_client = roleplay_client
        session.roleplay_config = get_config().roleplay

        revealed_ids = set(snapshot.get("revealed_clue_ids", []))
        for clue in archive.clues:
            clue.reveal_to_all = clue.id in revealed_ids or clue.reveal_to_all

        state_snapshot = dict(snapshot["state"])
        state_snapshot.setdefault("mode", mode)
        session.game.state = _restore_state(state_snapshot, archive)

        human_char = session.game.get_character(session.human_player_id)
        persona = (
            f"{human_char.name}（{human_char.public_identity}）"
            if human_char else ""
        )

        session.game.migrate_discussion_history()
        # Legacy private buffers mostly duplicate the public history. Preserve
        # unmatched entries as private quotations, without guessing chronology.
        if snapshot.get("schema_version", 1) < 2:
            for cid, memory in snapshot.get("ai_memories", {}).items():
                if cid not in session.game.state.player_states:
                    continue
                for entry in memory:
                    speaker = cid if entry.get("role") == "assistant" else session.human_player_id
                    text = entry.get("message", "")
                    if not isinstance(text, str) or not text:
                        continue
                    if any(e.speaker_id == speaker and e.text == text and
                           (not e.audience or cid in e.audience)
                           for e in session.game.state.discussion_events):
                        continue
                    session.game.add_discussion(speaker, text, audience=(cid,),
                                                kind="legacy_memory", legacy=True)
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
            "portrait_url": char.portrait_url,
            "role_script": char.role_script(),
            "objectives": char.objectives or ["根据证据找出凶手", "解释自己的行踪"],
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
                "portrait_url": c.portrait_url,
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

    def get_case_brief(self) -> Dict[str, Any]:
        """Public case synopsis — what a player may know before play starts.

        刻意排除 ``motive`` 与 ``true_killer``：动机与真凶是谜底，
        只在落幕揭晓时经 ``get_reveal_info`` 下发。
        """
        case = self.archive.case
        return {
            "title": case.title,
            "background": case.background,
            "victim": case.victim,
            "crime": case.crime,
            "location": case.location,
            "time": case.time,
        }

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
                "title": entry.clue.lead,
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
            if self.game.state.mode == "quick" and not self._investigated_this_round():
                actions.remove("discuss")
        elif phase == "discussion":
            actions = ["speak", "view_clues", "investigate", "accuse", "vote", "return_investigation"]
            if self.game.state.mode == "quick" and (
                self.game.state.round < self.game.state.max_rounds
                or not self._completed_this_round()
            ):
                actions.remove("vote")
            if (self.game.state.mode == "quick" and self._completed_this_round()
                    and self.game.state.round < self.game.state.max_rounds):
                actions.append("next_round")
        elif phase == "voting":
            actions = ["vote"]
        elif phase == "reveal":
            actions = []
        return {
            "game_id": self.game_id,
            "story_id": self.archive.id,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
            "is_speaking": self.is_speaking,
            "phase": phase,
            "mode": self.game.state.mode,
            "is_quick_mode": self.game.state.mode == "quick",
            "round": self.game.state.round,
            "max_rounds": self.game.state.max_rounds,
            "progress": {
                "current": min(self.game.state.round, self.game.state.max_rounds),
                "total": self.game.state.max_rounds,
            },
            "player": self.get_player_info(),
            "characters": self.get_all_characters(),
            "case_brief": self.get_case_brief(),
            "available_actions": actions,
            "investigation_count": self.game.state.investigation_count,
            "round_progress": {"investigated": self._investigated_this_round(),
                               "discussed": self.game.state.discussed_round == self.game.state.round},
            "investigation_options": self.get_investigation_options(),
            "last_event": self.game.state.last_event,
        }

    def get_reveal_info(self) -> Dict[str, Any]:
        if self.game.current_phase != GamePhase.REVEAL or not self.game.state.game_ended:
            raise GameError(status_code=400, detail="游戏尚未结束，不能查看真相")
        return {
            "story_content": self.archive.story_content,
            "winner": self.game.state.winner or "unknown",
            "case_info": {
                "title": self.archive.case.title,
                "background": self.archive.case.background,
                "victim": self.archive.case.victim,
                "crime": self.archive.case.crime,
                "motive": (self.game.get_character(self.game.killer_id).motive
                           if self.archive.case.motive in ("", "详见真相")
                           else self.archive.case.motive),
                "true_killer": self.game.killer_id,
                "true_killer_name": self._char_name(self.game.killer_id),
            },
            "characters": self.get_all_characters(include_private=True),
            "player_verdict": {
                "target": self._char_name(self.game.state.player_states[self.human_player_id].vote) if self.game.state.player_states[self.human_player_id].vote else "",
                "correct": self.game.state.winner == "good",
            },
            "advice_state": ("running" if self._busy else "completed"
                if len(self.pending_ballots['completed']) == len(self.pending_ballots['contexts']) else "available")
                if self.pending_ballots else "unavailable",
            "deductions": [{"conclusion": deduction['conclusion'], "evidence": [
                {"clue_id": ref['clue_id'], "title": self.game.get_clue(ref['clue_id']).lead,
                 "quote": ref['quote'], "discovered": ref['clue_id'] in {
                     c.id for c in self.game.get_player_clues(self.human_player_id) + self.game.get_revealed_clues()}}
                for ref in deduction['evidence']]} for deduction in self.archive.solution],
            "votes": self.game.state.ballot_details or [{"voter": self._char_name(v["player_id"]),
                       "target": self._char_name(v["target_id"]),
                       "reason": v.get("reason", "")} for v in self.game.state.votes_record],
        }

    def get_discussion_history(self) -> List[Dict[str, str]]:
        """Project the public event log onto the existing client API."""
        self.game.migrate_discussion_history()
        return [{"speaker": e.speaker_name, "message": e.text, "action_id": e.action_id, "kind": e.kind}
                for e in self.game.state.discussion_events if not e.audience]

    # -- context assembly ----------------------------------------------------

    def _ai_context(
        self, char_id: str, *, events: tuple[DiscussionEvent, ...] | None = None,
        action_id: str = "", current_event_id: str = "", user_input: str = "",
    ) -> Dict[str, Any]:
        """Freeze an allowed view before dispatching any worker for this action."""
        if events is None:
            self.game.migrate_discussion_history()
            events = tuple(self.game.state.discussion_events)
        ai = self.ai_characters[char_id]
        return {"context": ContextAssembler.assemble(
            character=ai.character, phase=self.game.current_phase, case=self.archive.case,
            known_clues=self.game.get_player_clues(char_id),
            revealed_clues=self.game.get_revealed_clues(),
            other_chars=[c for c in self.archive.characters if c.id in self.game.alive_players],
            events=events, user_input=user_input, user_persona=ai.user_persona,
            game_id=self.game_id, action_id=action_id,
            snapshot_seq=events[-1].sequence if events else 0, round=self.game.state.round,
            current_event_id=current_event_id, token_budget=self.roleplay_config.context_token_budget,
        )}

    # -- actions -------------------------------------------------------------

    async def player_introduce_async(self, message: str = "") -> Dict[str, Any]:
        """Collect introductions once; retries reuse the recorded statements."""
        self.ensure_playable()
        if self.game.current_phase != GamePhase.INTRODUCTION:
            raise GameError(status_code=400, detail="当前不是自我介绍阶段")
        self.game.migrate_discussion_history()
        if self.game.state.discussion_history:
            history = self.get_discussion_history()
            name = self._char_name(self.human_player_id)
            return {
                "player_introduction": next(m["message"] for m in history if m["speaker"] == name),
                "ai_introductions": [m for m in history if m["speaker"] != name],
                "new_phase": self.game.state.phase,
            }
        human_char = self.game.get_character(self.human_player_id)
        player_intro = message or (
            f"大家好，我是{human_char.name}，{human_char.public_identity}。"
        )


        action_id = str(uuid.uuid4())
        ai_introductions = []
        for ai in self.ai_characters.values():
            character = ai.character
            response = character.public_introduction or f"大家好，我是{character.name}，{character.public_identity}。"
            ai_introductions.append({"speaker": ai.name, "message": response,
                                     "action_id": action_id, "kind": "introduction"})
            self.game.add_discussion(
                ai.character_id, response, action_id=action_id, kind="introduction",
            )
        self.game.add_discussion(self.human_player_id, player_intro, action_id=action_id, kind="introduction")

        # Do NOT auto-advance the phase — the frontend shows the
        # introductions and explicitly moves to investigation.
        return {
            "player_introduction": player_intro,
            "ai_introductions": ai_introductions,
            "new_phase": self.game.state.phase,
        }

    def get_investigation_options(self) -> List[Dict[str, str]]:
        """Build short-mode investigation choices without exposing answers.

        Available in both the investigation phase and mid-discussion —
        the phase guard must mirror ``investigate()`` so advertised
        actions are actually callable.
        """
        if (
            self.game.state.mode != "quick"
            or self.game.current_phase not in (
                GamePhase.INVESTIGATION, GamePhase.DISCUSSION,
            )
        ):
            return []

        type_labels = {
            "physical": "物证",
            "testimony": "证词",
            "document": "文书",
        }
        options = []
        for clue in self.game.get_available_clues(self.human_player_id):
            label = type_labels.get(clue.type, "线索")
            source = "案发现场" if clue.holder_id == "scene" else self._char_name(clue.holder_id)
            lead = clue.lead or f"{source}的{label}"
            options.append({
                "id": clue.id,
                "title": f"调查{lead}",
                "description": f"第{self.game.state.round}轮 · 核对{source}的{label}，调查后获得结果。",
                "kind": clue.type,
            })
        return options

    @staticmethod
    def _event_for_clue(clue) -> Dict[str, str]:
        messages = {
            "physical": "现场出现新的物证，案发过程需要重新核对。",
            "testimony": "一份证词露出新的切口，相关人物值得继续追问。",
            "document": "一份记录被重新翻出，某人的行动轨迹出现变化。",
        }
        return {
            "type": "clue_breakthrough",
            "title": "案件出现突破",
            "message": messages.get(clue.type, "新的证据让案件向前推进了一步。"),
            "clue_id": clue.id,
        }

    def investigate(self, lead_id: Optional[str] = None) -> Dict[str, Any]:
        """Active investigation: draw a clue, optionally selected by the player.

        Usable in the investigation phase and mid-discussion; errors out
        when nothing remains to find.
        """
        self.ensure_playable()
        if self.game.current_phase not in (
            GamePhase.INVESTIGATION, GamePhase.DISCUSSION,
        ):
            raise GameError(status_code=400, detail="当前阶段不能搜证")

        if self.game.state.mode == "quick":
            options = self.get_investigation_options()
            if not options:
                raise GameError(status_code=400, detail="已经没有更多线索了")
            selected_id = lead_id or options[0]["id"]
            if selected_id not in {item["id"] for item in options}:
                raise GameError(status_code=400, detail="请选择当前可调查的方向")
            found = self.game.distribute_clue(self.human_player_id, selected_id)
        else:
            found = self.game.distribute_random_clues(self.human_player_id, 1)
        if not found:
            raise GameError(status_code=400, detail="已经没有更多线索了")
        self.game.state.investigated_round = self.game.state.round
        event = self._event_for_clue(found[0]) if self.game.state.mode == "quick" else None
        self.game.state.last_event = event
        return {
            "found": [
                {
                    "id": c.id,
                    "title": c.lead,
                    "content": c.content,
                    "type": c.type,
                    "holder_name": self._char_name(c.holder_id),
                }
                for c in found
            ],
            "clue_board": self.get_clue_board(),
            "investigation_options": self.get_investigation_options(),
            "event": event,
            "available_actions": self.get_game_status()["available_actions"],
        }

    def accuse(self, character_name: str) -> Dict[str, Any]:
        self.ensure_playable()
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise GameError(status_code=400, detail=f"找不到角色: {character_name}")
        correct, message = self.game.accuse(self.human_player_id, target_id)
        if not correct and "不能" in message:
            # domain rejected the target itself (self/dead) — surface as 400
            raise GameError(status_code=400, detail=message)
        return {
            "correct": correct,
            "message": message,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner,
        }

    def validate_discussion(self, target_id: Optional[str], clue_ids: list[str]) -> None:
        """Validate a directed question and evidence without revealing anything."""
        self.ensure_playable()
        if self.game.current_phase != GamePhase.DISCUSSION:
            raise GameError(status_code=400, detail="当前不是讨论阶段")
        if target_id and (target_id not in self.ai_characters or target_id not in self.game.alive_players):
            raise GameError(status_code=400, detail="请选择在场的其他角色")
        known = {c.id for c in self.game.get_player_clues(self.human_player_id)} | {
            c.id for c in self.game.get_revealed_clues()}
        if any(cid not in known for cid in clue_ids):
            raise GameError(status_code=400, detail="只能出示你已掌握的证据")

    async def player_speak_async(
        self, message: str, target_id: Optional[str] = None,
        presented_clue_ids: Optional[list[str]] = None, action_id: Optional[str] = None,
        include_question: bool = False,
    ) -> AsyncIterable[Dict[str, Any]]:
        """Stream a session-owned round that survives client disconnection.

        Recording and persistence happen in the background producer, never
        in the transport consumer. The session keeps the task alive until
        every worker has updated its memory and recorded its reply.
        """
        clue_ids = presented_clue_ids or []
        self.validate_discussion(target_id, clue_ids)
        self.game.present_clues(self.human_player_id, clue_ids)
        if target_id:
            message = f"【询问{self._char_name(target_id)}】{message}"
        if clue_ids:
            message += "\n【出示证据】" + "、".join(clue_ids)
        action_id = action_id or str(uuid.uuid4())
        current_event = self.game.add_discussion(
            self.human_player_id, message, action_id=action_id, kind="question",
            target_id=target_id, presented_clue_ids=tuple(clue_ids),
        )
        events = tuple(self.game.state.discussion_events)
        recipients = {cid: ai for cid, ai in self.ai_characters.items()
                      if cid in self.game.alive_players and (not target_id or cid == target_id)}
        try:
            contexts = {cid: self._ai_context(
                cid, events=events, action_id=action_id,
                current_event_id=current_event.event_id, user_input=message,
            ) for cid in recipients}
        except ContextBudgetExceeded as exc:
            await self._save_background()
            logger.warning("讨论上下文过大: %s", exc)
            raise GameError(status_code=413, detail="本案资料超过当前上下文容量") from exc
        self.pending_discussion = {
            'action_id': action_id, 'event_id': current_event.event_id,
            'message': message, 'phase': self.game.current_phase.value,
            'contexts': {cid: asdict(ctx['context']) for cid, ctx in contexts.items()},
            'completed': {},
        }
        await self._save_background()
        async for item in self.resume_speak_async(include_question=include_question):
            yield item

    async def resume_speak_async(self, include_question: bool = False) -> AsyncIterable[Dict[str, Any]]:
        """Continue a persisted round with its original frozen role contexts."""
        if self.is_speaking:
            raise GameError(409, '角色正在回应，请稍后再操作')
        pending = self.pending_discussion
        if not pending:
            return
        queue: asyncio.Queue = asyncio.Queue()
        phase = GamePhase(pending['phase'])

        async def respond(char_id: str, raw_context: dict) -> None:
            if char_id in pending['completed']:
                return
            ai = self.ai_characters[char_id]
            context = RoleContext.from_dict(raw_context)
            try:
                response = await asyncio.to_thread(ai.respond, user_input=pending['message'], phase=phase, context=context)
            except ModelInterrupted:
                raise
            except Exception as exc:
                logger.warning('角色 %s 回应失败: %s', ai.name, exc)
                response = '[回复失败]'
            self.game.add_discussion(
                char_id, response, action_id=pending['action_id'], reply_to=pending['event_id'],
                kind='delivery_error' if response == '[回复失败]' else 'statement',
                claims=getattr(response, 'claims', ()), corrections=getattr(response, 'corrections', ()),
            )
            message = {'speaker': ai.name, 'message': response,
                       'action_id': pending['action_id'], 'kind': 'delivery_error' if response == '[回复失败]' else 'statement'}
            pending['completed'][char_id] = message
            await self._save_background()
            queue.put_nowait(message)

        async def finish_round() -> None:
            try:
                results = await asyncio.gather(*(
                    respond(cid, ctx) for cid, ctx in pending['contexts'].items()
                ), return_exceptions=True)
                failure = next((r for r in results if isinstance(r, BaseException)), None)
                if failure:
                    queue.put_nowait(failure)
                else:
                    self.game.state.discussed_round = self.game.state.round
                    self.pending_discussion = None
            finally:
                await self._save_background()
                queue.put_nowait(None)

        self.discussion_task = asyncio.create_task(finish_round())
        if include_question:
            yield {'speaker': self._char_name(self.human_player_id), 'message': pending['message'],
                   'action_id': pending['action_id'], 'kind': 'question'}
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            yield item

    async def player_speak_collect(
        self, message: str, target_id: Optional[str] = None,
        presented_clue_ids: Optional[list[str]] = None, action_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Collect the same persistent round for the non-SSE client."""
        return [m async for m in self.player_speak_async(message, target_id, presented_clue_ids, action_id)]

    async def vote_async(self, character_name: str, action_id: Optional[str] = None) -> Dict[str, Any]:
        """Persist the player's verdict locally; NPC opinions are optional."""
        if (action_id and self.game.state.game_ended and self.pending_ballots
                and self.pending_ballots.get('action_id') == action_id):
            return self._verdict_payload("已保存你的最终判断")
        self.ensure_playable()
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id or target_id == self.human_player_id or target_id not in self.game.alive_players:
            raise GameError(400, "请选择有效嫌疑人，不能选择自己或已出局角色")
        if not self.game.can_vote(self.human_player_id):
            raise GameError(400, "当前无法投票")
        action_id = action_id or str(uuid.uuid4())
        events = tuple(self.game.state.discussion_events)
        contexts = {}
        for cid in self.ai_characters:
            if cid in self.game.alive_players:
                try:
                    contexts[cid] = asdict(self._ai_context(cid, events=events, action_id=action_id)['context'])
                except ContextBudgetExceeded:
                    logger.warning("角色 %s 表决上下文过大，跳过可选意见", cid)
        self.pending_ballots = {'action_id': action_id, 'contexts': contexts, 'completed': {}}
        self.game.submit_vote(self.human_player_id, target_id)
        _, result_msg = self.game.resolve_player_verdict(self.human_player_id)
        self.game.record_ballot_advice(self.human_player_id, target_id, "玩家最终判断")
        # Do not swallow a failed terminal save. Mobile also commits the task
        # and snapshot atomically before acknowledging completion.
        if is_embedded():
            self._persist()
        else:
            await asyncio.to_thread(self._persist)
        return self._verdict_payload(result_msg)

    def _verdict_payload(self, result_msg: str) -> Dict[str, Any]:
        """Public, repeatable response for an already committed verdict."""
        target_id = self.game.state.player_states[self.human_player_id].vote
        return {
            'votes': {self._char_name(self.human_player_id): self._char_name(target_id)},
            'vote_reasons': {}, 'result': result_msg, 'game_ended': True,
            'winner': self.game.state.winner, 'phase': self.game.state.phase,
            'all_submitted': True,
        }

    async def collect_ballot_advice(self) -> Dict[str, Any]:
        """Collect optional terminal opinions; completed roles never run again."""
        if not self.game.state.game_ended or self.game.current_phase != GamePhase.REVEAL:
            raise GameError(400, "请先完成最终判断")
        if self._busy:
            raise GameError(409, "人物判断正在生成")
        pending = self.pending_ballots
        if not pending or len(pending['completed']) == len(pending['contexts']):
            return self.get_reveal_info()

        async def collect(cid: str, raw: dict) -> None:
            if cid in pending['completed']:
                return
            ai = self.ai_characters[cid]
            context = RoleContext.from_dict(raw)
            chosen, reason = '', ''
            try:
                async with asyncio.timeout(None if is_embedded() else NPC_VOTE_TIMEOUT_SECONDS):
                    for _ in range(2):
                        chosen, reason = await asyncio.to_thread(ai.get_vote, context=context)
                        if chosen in self.game.alive_players and chosen != cid:
                            break
                        chosen = ''
            except ModelInterrupted:
                raise
            except TimeoutError:
                reason = "人物判断超时，弃权"
            except Exception:
                reason = "未能完成判断，弃权"
            if chosen not in self.game.alive_players or chosen == cid:
                chosen = ''
            self.game.record_ballot_advice(cid, chosen, reason or ("未提供理由" if chosen else "未能完成判断，弃权"))
            pending['completed'][cid] = True
            await self._save_background()

        self._busy = True
        try:
            results = await asyncio.gather(*(collect(cid, raw) for cid, raw in pending['contexts'].items()),
                                           return_exceptions=True)
            failure = next((r for r in results if isinstance(r, BaseException)), None)
            if failure:
                raise failure
        finally:
            self._busy = False
            await self._save_background()
        return self.get_reveal_info()


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
        self._save_lock = threading.Lock()

    def create_session(
        self,
        topic: Optional[str] = None,
        archive: Optional[StoryArchive] = None,
        mode: str = "classic",
        game_id: Optional[str] = None,
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

        if archive.case.true_killer not in {c.id for c in archive.characters}:
            raise ValueError("剧本缺少有效的凶手身份")
        char_ids = [c.id for c in archive.characters
                    if c.id != archive.case.true_killer and not c.is_killer]
        if not char_ids:
            raise ValueError("剧本没有可供玩家扮演的非凶手角色")
        human_id = random.choice(char_ids)
        game_id = game_id or str(uuid.uuid4())
        if game_id in self._sessions:
            return game_id, self._sessions[game_id]
        session = GameSession(archive, human_id, self._roleplay_client, mode=mode, game_id=game_id)
        session.set_persistence_callback(lambda: self.save(game_id))
        self._sessions[game_id] = session
        self._store.save(session.to_snapshot(game_id))
        logger.info("Created session %s for story %s", game_id, archive.id)
        return game_id, session

    def get(self, game_id: str) -> GameSession:
        session = self._sessions.get(game_id)
        if not session:
            raise GameError(status_code=404, detail="游戏不存在")
        return session

    def save(self, game_id: str) -> None:
        session = self._sessions.get(game_id)
        if session is None:
            return
        with self._save_lock:
            session.last_activity = time.time()
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
            self._sessions[game_id].set_persistence_callback(lambda gid=game_id: self.save(gid))
            count += 1
        if count:
            logger.info("Restored %d session(s) from disk", count)
        return count

    def list_active(self) -> list[str]:
        return list(self._sessions.keys())
