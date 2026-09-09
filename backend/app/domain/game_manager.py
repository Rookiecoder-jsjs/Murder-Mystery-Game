# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game manager - controls game flow and voting logic."""

from collections import Counter
from typing import Optional
import random

from app.core.phases import GamePhase
from app.domain.models import (
    StoryArchive,
    ScriptCharacter,
    ClueData,
    GameState,
    PlayerState,
    ClueStatus,
    ClueBoardEntry,
    ClueBoard,
)


def majority_vote(votes: list[str]) -> tuple[str, str]:
    """Count votes and return the player with most votes.

    On a tie the winner is chosen uniformly at random among the tied
    candidates — never by ID ordering.

    Args:
        votes: List of voted character IDs.

    Returns:
        (winner_id, vote_summary_string)
    """
    if not votes:
        return "", "无投票"

    counts = Counter(votes)
    conditions = ", ".join(f"{name}: {count}" for name, count in counts.items())

    max_count = max(counts.values())
    tied = [name for name, count in counts.items() if count == max_count]
    winner = random.choice(tied)

    return winner, conditions


class GameManager:
    """Murder mystery game manager."""

    def __init__(self, archive: StoryArchive, mode: str = "classic"):
        """Initialize the game manager.

        Args:
            archive: The story archive containing characters and clues.
        """
        self.archive = archive
        normalized_mode = mode if mode in {"classic", "quick"} else "classic"
        self.state = GameState(
            story_id=archive.id,
            mode=normalized_mode,
            phase=GamePhase.INTRODUCTION.value,
            turn=0,
            round=1,
            max_rounds=3 if normalized_mode == "quick" else 5,
        )

        for char in archive.characters:
            self.state.player_states[char.id] = PlayerState(
                character_id=char.id,
            )

    @property
    def characters(self) -> dict[str, ScriptCharacter]:
        """Get character dictionary."""
        return {c.id: c for c in self.archive.characters}

    @property
    def clues(self) -> dict[str, ClueData]:
        """Get clue dictionary."""
        return {c.id: c for c in self.archive.clues}

    @property
    def alive_players(self) -> list[str]:
        """Get list of alive player IDs."""
        return [
            pid for pid, state in self.state.player_states.items()
            if state.is_alive
        ]

    @property
    def killer_id(self) -> str:
        """Get the killer's character ID."""
        return self.archive.case.true_killer

    @property
    def current_phase(self) -> GamePhase:
        """Get the current game phase."""
        return GamePhase(self.state.phase)

    def get_character(self, character_id: str) -> Optional[ScriptCharacter]:
        """Get a character by ID."""
        return self.characters.get(character_id)

    def get_character_id_by_name(self, name: str) -> Optional[str]:
        """Find character ID by name."""
        for char in self.archive.characters:
            if char.name == name:
                return char.id
        return None

    def get_clue(self, clue_id: str) -> Optional[ClueData]:
        """Get a clue by ID."""
        return self.clues.get(clue_id)

    def get_revealed_clues(self) -> list[ClueData]:
        """Get all revealed clues."""
        return [c for c in self.archive.clues if c.reveal_to_all]

    def get_player_clues(self, player_id: str) -> list[ClueData]:
        """Get all clues known by a player.

        Args:
            player_id: The player's character ID.

        Returns:
            List of ClueData known by the player.
        """
        state = self.state.player_states.get(player_id)
        if not state:
            return []

        return [
            self.get_clue(cid)
            for cid in state.known_clues
            if self.get_clue(cid)
        ]

    def next_phase(self) -> GamePhase:
        """Transition to the next phase.

        Returns:
            The new current phase.
        """
        current_phase = self.current_phase
        next_phase = GamePhase.next(current_phase)
        self.state.phase = next_phase.value
        self.state.turn = 0
        if next_phase == GamePhase.DISCUSSION:
            self.state.round = 1
        return next_phase

    def set_phase(self, phase: GamePhase) -> None:
        """Set the current phase directly.

        Args:
            phase: The phase to set.
        """
        self.state.phase = phase.value
        self.state.turn = 0
        if phase == GamePhase.DISCUSSION:
            self.state.round = 1

    def get_clue_board(self, player_id: str) -> ClueBoard:
        """Get the complete clue board for a player.

        Clues whose ``required_clue_id`` prerequisite the player has not
        obtained are excluded entirely — they are hidden, not merely
        marked unavailable.

        Args:
            player_id: The player's character ID.

        Returns:
            ClueBoard with all clues categorized.
        """
        state = self.state.player_states.get(player_id)
        if not state:
            return ClueBoard()

        owned_entries = []
        available_entries = []
        scene_public_entries = []

        known = set(state.known_clues)
        for clue in self.archive.clues:
            if clue.reveal_to_all and clue.holder_id == "scene":
                entry = ClueBoardEntry(
                    clue=clue,
                    status=ClueStatus.SCENE_PUBLIC.value,
                )
                scene_public_entries.append(entry)
                continue

            if clue.id in known:
                entry = ClueBoardEntry(
                    clue=clue,
                    status=ClueStatus.OWNED.value,
                )
                owned_entries.append(entry)
                continue

            if clue.required_clue_id and clue.required_clue_id not in known:
                continue  # locked — hidden from this player's board

            entry = ClueBoardEntry(
                clue=clue,
                status=ClueStatus.AVAILABLE.value,
            )
            available_entries.append(entry)

        return ClueBoard(
            owned=tuple(owned_entries),
            available=tuple(available_entries),
            scene_public=tuple(scene_public_entries),
        )

    def get_available_clues(self, player_id: str) -> list[ClueData]:
        """Return currently discoverable clues in archive order."""
        return [entry.clue for entry in self.get_clue_board(player_id).available]

    def _claim_clue(self, player_id: str, clue_id: str) -> Optional[ClueData]:
        """Claim one currently available clue without changing counters."""
        state = self.state.player_states.get(player_id)
        if not state:
            return None

        entry = next(
            (
                item
                for item in self.get_clue_board(player_id).available
                if item.clue.id == clue_id
            ),
            None,
        )
        if entry is None:
            return None

        state.known_clues.append(entry.clue.id)
        if entry.clue.holder_id == "scene":
            entry.clue.reveal_to_all = True
        return entry.clue

    def distribute_clue(self, player_id: str, clue_id: str) -> list[ClueData]:
        """Distribute a specific clue selected by the player."""
        claimed = self._claim_clue(player_id, clue_id)
        if claimed is None:
            return []
        self.state.investigation_count += 1
        return [claimed]

    def distribute_random_clues(
        self,
        player_id: str,
        count: int = 1,
    ) -> list[ClueData]:
        """Randomly distribute clues to a player.

        Locked clues (unmet ``required_clue_id``) are never distributed;
        obtaining a prerequisite unlocks the dependent clue for later
        draws. Scene-held clues become publicly revealed once found.

        Args:
            player_id: The player's character ID.
            count: Number of clues to distribute.

        Returns:
            List of distributed clues.
        """
        state = self.state.player_states.get(player_id)
        if not state:
            return []

        board = self.get_clue_board(player_id)
        available = list(board.available)

        if not available:
            return []

        selected = random.sample(available, min(count, len(available)))

        distributed = []
        for entry in selected:
            claimed = self._claim_clue(player_id, entry.clue.id)
            if claimed is not None:
                distributed.append(claimed)

        if distributed:
            self.state.investigation_count += 1
        return distributed

    def can_accuse(self, player_id: str) -> bool:
        """Check if a player can accuse someone.

        Args:
            player_id: The player's character ID.

        Returns:
            True if the player can accuse.
        """
        state = self.state.player_states.get(player_id)
        if not state or not state.is_alive:
            return False
        if state.accusation_points < 1:
            return False
        if state.has_accused:
            return False
        return True

    def accuse(
        self,
        player_id: str,
        target_id: str,
    ) -> tuple[bool, str]:
        """Player accuses a suspect.

        Args:
            player_id: The accusing player's character ID.
            target_id: The accused character's ID.

        Returns:
            (is_correct, result_description)
        """
        state = self.state.player_states.get(player_id)
        if not self.can_accuse(player_id):
            return False, "无法指认"

        if target_id == player_id:
            return False, "不能指认自己"

        target_state = self.state.player_states.get(target_id)
        if not target_state or not target_state.is_alive:
            return False, "不能指认已出局的角色"

        state.accusation_points -= 1
        state.has_accused = True

        if target_id == self.killer_id:
            char = self.get_character(target_id)
            self.state.phase = GamePhase.REVEAL.value
            self.state.game_ended = True
            self.state.winner = "good"
            return True, (
                f"你指认了 {char.name if char else target_id}，"
                f"正确！凶手被抓！好人胜利！"
            )
        else:
            char = self.get_character(target_id)
            killer = self.get_character(self.killer_id)
            self.state.phase = GamePhase.REVEAL.value
            self.state.game_ended = True
            self.state.winner = "killer"
            return False, (
                f"你指认了 {char.name if char else target_id}，错误！\n"
                f"真凶是 {killer.name if killer else self.killer_id}！\n"
                f"凶手逃脱，好人失败..."
            )

    def submit_vote(
        self,
        player_id: str,
        target_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Submit a vote for a player.

        A vote replaces any earlier vote by the same player (revote
        support) and never duplicates.

        Args:
            player_id: The voting player's character ID.
            target_id: The voted character's ID.
            reason: Optional one-line reason (AI votes carry it); kept in
                the record for reveal/logging but never influences tally.

        Returns:
            True if the vote was recorded.
        """
        state = self.state.player_states.get(player_id)
        if not state or not state.is_alive:
            return False
        if self.current_phase != GamePhase.VOTING:
            return False

        self.state.votes_record = [
            v for v in self.state.votes_record
            if v["player_id"] != player_id
        ]
        state.vote = target_id
        record = {"player_id": player_id, "target_id": target_id}
        if reason:
            record["reason"] = reason
        self.state.votes_record.append(record)
        return True

    def reset_votes(self) -> None:
        """Clear all recorded votes (start of a fresh voting round)."""
        self.state.votes_record = []
        for state in self.state.player_states.values():
            state.vote = None

    def can_vote(self, player_id: str) -> bool:
        """Check whether a player may vote in the current phase."""
        state = self.state.player_states.get(player_id)
        return bool(
            state and state.is_alive
            and self.current_phase == GamePhase.VOTING
        )

    def get_votes(self) -> list[str]:
        """Get all votes.

        Returns:
            List of voted character IDs.
        """
        return [v["target_id"] for v in self.state.votes_record]

    def tally_votes(self) -> tuple[str, str, bool]:
        """Tally all votes.

        Returns:
            (winner_id, vote_summary, is_tied)
        """
        votes = self.get_votes()
        if not votes:
            return "", "无投票", False

        winner, conditions = majority_vote(votes)

        vote_counts = {}
        for v in votes:
            vote_counts[v] = vote_counts.get(v, 0) + 1

        max_votes = max(vote_counts.values())
        tied_players = [p for p, c in vote_counts.items() if c == max_votes]
        is_tied = len(tied_players) > 1

        return winner, conditions, is_tied

    def eliminate_player(self, player_id: str) -> bool:
        """Eliminate a player from the game.

        Args:
            player_id: The character ID to eliminate.

        Returns:
            True if elimination was successful.
        """
        state = self.state.player_states.get(player_id)
        if not state or not state.is_alive:
            return False

        state.is_alive = False
        self.state.eliminated_id = player_id
        return True

    def check_voting_result(self) -> tuple[bool, str]:
        """Check the voting result.

        Only votes from currently-alive players are counted; a vote from
        an already-eliminated player is ignored.

        Returns:
            (game_ended, result_description)
        """
        if self.current_phase != GamePhase.VOTING:
            return False, ""

        alive_votes = [
            v["target_id"] for v in self.state.votes_record
            if self.state.player_states.get(
                v["player_id"], PlayerState("")
            ).is_alive
        ]

        if len(alive_votes) < len(self.alive_players):
            return False, "等待投票中..."

        winner, conditions, is_tied = self.tally_votes()

        total_alive = len(self.alive_players)
        required_votes = (total_alive * 2) // 3 + 1

        votes_for_winner = sum(1 for v in alive_votes if v == winner)

        if is_tied:
            return False, f"投票平局: {conditions}"

        if votes_for_winner >= required_votes:
            self.eliminate_player(winner)
            char = self.get_character(winner)

            if winner == self.killer_id:
                self.state.phase = GamePhase.REVEAL.value
                self.state.game_ended = True
                self.state.winner = "good"
                return True, (
                    f"投票结果: {conditions}\n"
                    f"{char.name}被淘汰！\n"
                    f"凶手是{char.name}！好人胜利！"
                )
            else:
                self.state.phase = GamePhase.REVEAL.value
                self.state.game_ended = True
                self.state.winner = "killer"
                return True, (
                    f"投票结果: {conditions}\n"
                    f"{char.name}被淘汰！\n"
                    f"但{char.name}不是凶手！凶手逃脱！"
                )
        else:
            return False, (
                f"票数不足: {conditions}，需要{required_votes}票才能淘汰"
            )

    def force_reveal(self) -> None:
        """Force the game into the reveal phase."""
        self.state.phase = GamePhase.REVEAL.value
        self.state.game_ended = True

    def add_discussion(self, player_id: str, message: str) -> None:
        """Add a message to the discussion history.

        Args:
            player_id: The speaking player's character ID.
            message: The spoken message.
        """
        char = self.get_character(player_id)
        char_name = char.name if char else player_id
        self.state.discussion_history.append(f"{char_name}: {message}")

    def get_game_summary(self) -> str:
        """Get a summary of the game result.

        Returns:
            Game summary string.
        """
        result = []
        result.append(f"=== {self.archive.title} ===")
        result.append(f"\n【案件背景】\n{self.archive.case.background}")
        result.append(f"\n【受害者】{self.archive.case.victim}")
        result.append(f"\n【死者信息】{self.archive.case.crime}")
        result.append(f"\n【游戏结果】")

        if self.state.winner == "good":
            result.append("好人胜利！凶手被成功指认！")
        elif self.state.winner == "killer":
            result.append("凶手逃脱！好人失败...")
        else:
            result.append("游戏未结束")

        result.append(f"\n【真相】\n{self.archive.story_content}")

        return "\n".join(result)
