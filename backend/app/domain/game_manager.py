"""Game manager - controls game flow and voting logic."""

from collections import Counter
from typing import Optional
import random

from app.core.phases import GamePhase
from app.domain.context import DiscussionEvent, StatementClaim
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


VALID_MODES = {"classic", "quick"}
"""All supported game modes."""


def normalize_mode(mode: str) -> str:
    """Map unknown mode values onto the classic default.

    Shared by ``GameManager.__init__`` and snapshot restore so a
    corrupted or future-unknown mode can never silently run as
    something the game wasn't created with.
    """
    return mode if mode in VALID_MODES else "classic"


def max_rounds_for_mode(mode: str) -> int:
    """Round cap for a mode (quick counts investigation rounds)."""
    return 3 if mode == "quick" else 5


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
        self._release_rounds = archive.release_rounds()
        mode = normalize_mode(mode)
        self.state = GameState(
            story_id=archive.id,
            mode=mode,
            phase=GamePhase.INTRODUCTION.value,
            turn=0,
            round=1,
            max_rounds=max_rounds_for_mode(mode),
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
        """Scene discoveries and explicitly presented personal evidence."""
        return [c for c in self.archive.clues if c.reveal_to_all]

    def present_clues(self, player_id: str, clue_ids: list[str]) -> None:
        """Publish owned evidence; validate the entire batch before mutation."""
        known = {c.id for c in self.get_player_clues(player_id)} | {
            c.id for c in self.get_revealed_clues()}
        if any(cid not in known for cid in clue_ids):
            raise ValueError("只能出示你已掌握的证据")
        for cid in clue_ids:
            self.get_clue(cid).reveal_to_all = True

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
        nxt = GamePhase.next(self.current_phase)
        self.set_phase(nxt)
        return nxt

    def set_phase(self, phase: GamePhase) -> None:
        """Set the current phase directly.

        Single owner of the transition policy (turn reset,
        discussion-entry round semantics, transient banner clearing) so
        the next_phase path and direct-set paths can never drift apart.

        Args:
            phase: The phase to set.
        """
        if self.state.game_ended and phase != GamePhase.REVEAL:
            raise ValueError("游戏已经结束")
        self.state.phase = phase.value
        self.state.turn = 0
        if phase == GamePhase.DISCUSSION and self.state.mode != "quick":
            # 经典模式：round 计讨论发言轮次，进入讨论时归 1。
            # 速推模式：round 计调查轮次，必须原样带入讨论，否则
            # return-to-investigation 的累加会被清空，投票门槛永不可达。
            self.state.round = 1
        # 突发事件横幅只属于触发它的那一刻，阶段推进后不再展示
        self.state.last_event = None

    def start_next_investigation_round(self, player_id: str) -> None:
        """Advance a completed quick round only through an explicit action."""
        investigated = (self.state.investigated_round == self.state.round
                        or not self.get_available_clues(player_id))
        if (self.state.game_ended or self.state.mode != "quick"
                or self.current_phase != GamePhase.DISCUSSION
                or self.state.round >= self.state.max_rounds
                or not investigated or self.state.discussed_round != self.state.round):
            raise ValueError("请完成本轮调查和讨论后再开启下一轮")
        self.state.round += 1
        self.set_phase(GamePhase.INVESTIGATION)

    def record_ballot_advice(self, player_id: str, target_id: str, reason: str) -> None:
        """Store optional terminal advice without changing votes or the verdict."""
        if not self.state.game_ended or self.current_phase != GamePhase.REVEAL:
            raise ValueError("结案后才能记录人物判断")
        character = self.get_character(player_id)
        target = self.get_character(target_id)
        if not character or (target_id and (not target or target_id == player_id)):
            raise ValueError("人物判断的角色无效")
        self.state.ballot_details = [b for b in self.state.ballot_details if b["voter"] != character.name]
        self.state.ballot_details.append({"voter": character.name,
            "target": target.name if target else "弃权", "reason": reason})

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
        # 已公开的线索对所有人都是已知的，理应满足解锁前置。漏掉这一步
        # 会让链条断死：场景线索一旦被抽到就转公开、走上面的 scene_public
        # 分支，永远不会进入 known_clues，于是依赖它的线索对该玩家永久隐藏。
        satisfied = known | {
            c.id for c in self.archive.clues if c.reveal_to_all
        }
        for clue in self.archive.clues:
            if clue.reveal_to_all:
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

            if clue.required_clue_id and clue.required_clue_id not in satisfied:
                continue  # locked — hidden from this player's board

            if self.state.mode == "quick" and self._release_rounds.get(clue.id, 1) > self.state.round:
                continue

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

    @staticmethod
    def validate_quick_evidence_routes(archive: StoryArchive) -> None:
        """Authoring-only simulation of evidence access for each playable role.

        It checks rule reachability, not whether quotations prove a conclusion.
        Each simulation owns a fresh archive, so no public flags escape to play.
        """
        required = {ref['clue_id'] for step in archive.solution for ref in step['evidence']}
        for character in archive.characters:
            if character.id == archive.case.true_killer:
                continue
            game = GameManager(StoryArchive.from_dict(archive.to_dict()), mode="quick")
            game.set_phase(GamePhase.INVESTIGATION)
            for round_number in (1, 2, 3):
                game.state.round = round_number
                for role_id in game.alive_players:
                    game.grant_role_clues(role_id)
                while available := game.get_available_clues(character.id):
                    game.distribute_clue(character.id, available[0].id)
            visible = {c.id for c in game.get_player_clues(character.id) + game.get_revealed_clues()}
            if missing := required - visible:
                raise ValueError(f"角色 {character.id} 在三轮内无法取得定案证据：{'、'.join(sorted(missing))}")

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
        exclude_scene: bool = False,
    ) -> list[ClueData]:
        """Randomly distribute clues to a player.

        Locked clues (unmet ``required_clue_id``) are never distributed;
        obtaining a prerequisite unlocks the dependent clue for later
        draws. Scene-held clues become publicly revealed once found.

        Args:
            player_id: The player's character ID.
            count: Number of clues to distribute.
            exclude_scene: Skip scene-held clues. Quick mode reserves
                them as the human's investigation leads — an AI claiming
                one reveals it publicly and shrinks the lead options.

        Returns:
            List of distributed clues.
        """
        state = self.state.player_states.get(player_id)
        if not state:
            return []

        board = self.get_clue_board(player_id)
        available = list(board.available)
        if exclude_scene:
            available = [
                entry for entry in available
                if entry.clue.holder_id != "scene"
            ]

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
        if self.state.game_ended or self.current_phase == GamePhase.REVEAL:
            return False
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
        state.vote = target_id  # Preserve the final choice for the reveal.

        if target_id == self.killer_id:
            char = self.get_character(target_id)
            self.set_phase(GamePhase.REVEAL)
            self.state.game_ended = True
            self.state.winner = "good"
            return True, (
                f"你指认了 {char.name if char else target_id}，"
                f"正确！凶手被抓！好人胜利！"
            )
        else:
            char = self.get_character(target_id)
            killer = self.get_character(self.killer_id)
            self.set_phase(GamePhase.REVEAL)
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

    def resolve_player_verdict(self, player_id: str) -> tuple[bool, str]:
        """A single human's final answer determines their outcome; NPCs advise."""
        if self.state.game_ended or not self.can_vote(player_id):
            return False, "当前无法结案"
        target = self.state.player_states[player_id].vote
        target_state = self.state.player_states.get(target)
        if target == player_id or not target_state or not target_state.is_alive:
            return False, "请先选择有效嫌疑人"
        correct = target == self.killer_id
        self.set_phase(GamePhase.REVEAL)
        self.state.game_ended = True
        self.state.winner = "good" if correct else "killer"
        name = self.get_character(target).name
        return True, f"你的最终判断：{name}。" + ("指认正确，好人胜利！" if correct else "指认错误，凶手逃脱。")

    def grant_role_clues(self, player_id: str) -> None:
        """Give only this role's authored personal knowledge, without searching."""
        character = self.get_character(player_id)
        if not character:
            return
        eligible = set(character.clues)
        # Repeat to allow a role's own prerequisite chain in the same release.
        while True:
            clues = [c for c in self.get_available_clues(player_id)
                     if c.id in eligible and c.holder_id == player_id]
            if not clues:
                break
            for clue in clues:
                self._claim_clue(player_id, clue.id)

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
                self.set_phase(GamePhase.REVEAL)
                self.state.game_ended = True
                self.state.winner = "good"
                return True, (
                    f"投票结果: {conditions}\n"
                    f"{char.name}被淘汰！\n"
                    f"凶手是{char.name}！好人胜利！"
                )
            else:
                self.set_phase(GamePhase.REVEAL)
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
        self.set_phase(GamePhase.REVEAL)
        self.state.game_ended = True

    def migrate_discussion_history(self) -> None:
        """Import old public lines once, without inventing missing metadata."""
        if self.state.discussion_events:
            self._refresh_discussion_projection()
            return
        by_name = {c.name: c.id for c in self.archive.characters}
        for line in self.state.discussion_history:
            name, separator, text = line.partition(": ")
            sequence = len(self.state.discussion_events) + 1
            self.state.discussion_events.append(DiscussionEvent(
                event_id=f"e{sequence}", sequence=sequence,
                speaker_id=by_name.get(name, ""), speaker_name=name if separator else "未知",
                text=text if separator else line, kind="legacy_statement",
            ))

    def _refresh_discussion_projection(self) -> None:
        self.state.discussion_history = [
            f"{e.speaker_name}: {e.text}" for e in self.state.discussion_events
            if not e.audience
        ]

    def add_discussion(
        self, player_id: str, message: str, *, action_id: str = "",
        kind: str = "statement", target_id: str | None = None,
        presented_clue_ids: tuple[str, ...] = (), reply_to: str | None = None,
        audience: tuple[str, ...] = (), claims: tuple[StatementClaim, ...] = (),
        corrections: tuple[str, ...] = (), legacy: bool = False,
    ) -> DiscussionEvent:
        """Append a sourced utterance and update the public compatibility view."""
        self.migrate_discussion_history()
        char = self.get_character(player_id)
        char_name = char.name if char else player_id
        sequence = self.state.discussion_events[-1].sequence + 1 if self.state.discussion_events else 1
        event = DiscussionEvent(
            event_id=f"e{sequence}", sequence=sequence,
            speaker_id=player_id, speaker_name=char_name, text=str(message),
            phase=None if legacy else self.state.phase,
            round=None if legacy else self.state.round,
            action_id=action_id, kind=kind, target_id=target_id,
            presented_clue_ids=tuple(presented_clue_ids), reply_to=reply_to,
            audience=tuple(audience), claims=tuple(claims), corrections=tuple(corrections),
        )
        self.state.discussion_events.append(event)
        self._refresh_discussion_projection()
        return event

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
