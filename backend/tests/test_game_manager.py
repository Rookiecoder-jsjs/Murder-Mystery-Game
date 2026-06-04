# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Unit tests for GameManager — phase transitions, voting, clues, accuse."""

from __future__ import annotations

import pytest

from app.core.phases import GamePhase
from app.domain.game_manager import GameManager, majority_vote
from app.domain.models import ClueStatus


# ---------- majority_vote ----------

class TestMajorityVote:
    def test_empty_returns_empty(self):
        winner, summary = majority_vote([])
        assert winner == ""
        assert "无投票" in summary

    def test_single_winner(self):
        winner, summary = majority_vote(["a", "b", "b", "c"])
        assert winner == "b"
        assert "a: 1" in summary
        assert "b: 2" in summary

    def test_picks_first_on_tie(self):
        winner, _ = majority_vote(["a", "b", "a", "b"])
        assert winner in ("a", "b")


# ---------- Initialization ----------

class TestInit:
    def test_starts_in_introduction(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.current_phase == GamePhase.INTRODUCTION

    def test_player_states_created(self, sample_archive):
        gm = GameManager(sample_archive)
        assert set(gm.state.player_states.keys()) == {
            "char_1", "char_2", "char_3", "char_4"
        }
        for ps in gm.state.player_states.values():
            assert ps.is_alive
            assert ps.accusation_points == 1
            assert not ps.has_accused

    def test_alive_players(self, sample_archive):
        gm = GameManager(sample_archive)
        assert len(gm.alive_players) == 4

    def test_killer_id(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.killer_id == "char_1"


# ---------- Phase transitions ----------

class TestPhaseTransitions:
    def test_next_phase_intro_to_investigation(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.next_phase()
        assert gm.current_phase == GamePhase.INVESTIGATION

    def test_next_phase_full_sequence(self, sample_archive):
        gm = GameManager(sample_archive)
        expected = [
            GamePhase.INVESTIGATION,
            GamePhase.DISCUSSION,
            GamePhase.VOTING,
            GamePhase.REVEAL,
        ]
        for phase in expected:
            gm.next_phase()
            assert gm.current_phase == phase

    def test_next_phase_at_reveal_stays(self, sample_archive):
        gm = GameManager(sample_archive)
        for _ in range(10):
            gm.next_phase()
        assert gm.current_phase == GamePhase.REVEAL
        gm.next_phase()
        assert gm.current_phase == GamePhase.REVEAL

    def test_next_phase_resets_turn(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.state.turn = 5
        gm.next_phase()
        assert gm.state.turn == 0

    def test_next_phase_into_discussion_resets_round(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.next_phase()  # -> investigation
        gm.next_phase()  # -> discussion
        assert gm.state.round == 1
        gm.state.round = 3
        gm.next_phase()  # -> voting
        gm.next_phase()  # -> reveal
        # Re-entering discussion (via set_phase) resets round to 1
        gm.set_phase(GamePhase.DISCUSSION)
        assert gm.state.round == 1

    def test_set_phase_directly(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.DISCUSSION)
        assert gm.current_phase == GamePhase.DISCUSSION
        assert gm.state.turn == 0


# ---------- Character / Clue lookups ----------

class TestLookups:
    def test_get_character(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.get_character("char_1").name == "Alice"
        assert gm.get_character("nope") is None

    def test_get_character_id_by_name(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.get_character_id_by_name("Alice") == "char_1"
        assert gm.get_character_id_by_name("Nobody") is None

    def test_get_clue(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.get_clue("clue_a").content == "线索clue_a的内容"
        assert gm.get_clue("missing") is None

    def test_get_revealed_clues(self, sample_archive):
        gm = GameManager(sample_archive)
        revealed = gm.get_revealed_clues()
        assert {c.id for c in revealed} == {"clue_scene"}


# ---------- Clue board ----------

class TestClueBoard:
    def test_initial_board_separates_owned_available_scene(self, sample_archive):
        gm = GameManager(sample_archive)
        board = gm.get_clue_board("char_2")
        assert len(board.owned) == 0
        # 5 available (4 char clues + 1 locked clue) + 1 scene_public
        assert len(board.available) == 5
        assert len(board.scene_public) == 1
        assert board.scene_public[0].clue.id == "clue_scene"
        assert board.scene_public[0].status == ClueStatus.SCENE_PUBLIC.value

    def test_distribute_random_clues_marks_owned(self, sample_archive):
        gm = GameManager(sample_archive)
        distributed = gm.distribute_random_clues("char_2", count=2)
        assert len(distributed) == 2
        board = gm.get_clue_board("char_2")
        assert len(board.owned) == 2
        assert len(board.available) == 3  # 5 - 2

    def test_distribute_scene_clue_marks_revealed(self, sample_archive):
        """When the only available clue is held by the scene, distributing
        it must mark it as revealed to all."""
        from app.domain.models import ClueData
        # Replace the archive with one where the only available clue is
        # a scene-held one — guarantees the distribution path hits the
        # `if entry.clue.holder_id == "scene"` branch.
        scene_only = ClueData(
            id="clue_only_scene", content="x", type="physical",
            holder_id="scene", reveal_to_all=False,
        )
        sample_archive.clues = [scene_only]
        gm = GameManager(sample_archive)
        gm.distribute_random_clues("char_2", count=1)
        assert scene_only.reveal_to_all is True

    def test_distribute_no_available_returns_empty(self, sample_archive):
        gm = GameManager(sample_archive)
        for _ in range(20):
            gm.distribute_random_clues("char_2", count=10)
        board = gm.get_clue_board("char_2")
        assert len(board.available) == 0

    def test_get_player_clues_unknown_player_empty(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.get_player_clues("nobody") == []


# ---------- Accuse ----------

class TestAccuse:
    def test_can_accuse_initially(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.can_accuse("char_2") is True

    def test_cannot_accuse_after_use(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.accuse("char_2", "char_3")
        assert gm.can_accuse("char_2") is False

    def test_cannot_accuse_dead(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.eliminate_player("char_2")
        assert gm.can_accuse("char_2") is False

    def test_cannot_accuse_no_points(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.state.player_states["char_2"].accusation_points = 0
        assert gm.can_accuse("char_2") is False

    def test_accuse_correct_ends_game_good_wins(self, sample_archive):
        gm = GameManager(sample_archive)
        correct, msg = gm.accuse("char_2", "char_1")
        assert correct is True
        assert gm.state.game_ended is True
        assert gm.state.winner == "good"
        assert gm.current_phase == GamePhase.REVEAL
        assert "Alice" in msg

    def test_accuse_wrong_ends_game_killer_wins(self, sample_archive):
        gm = GameManager(sample_archive)
        correct, msg = gm.accuse("char_2", "char_3")
        assert correct is False
        assert gm.state.game_ended is True
        assert gm.state.winner == "killer"
        assert gm.current_phase == GamePhase.REVEAL
        assert "Alice" in msg


# ---------- Voting ----------

class TestVoting:
    def test_submit_vote_records(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        assert gm.submit_vote("char_1", "char_2") is True
        assert gm.state.votes_record[-1] == {
            "player_id": "char_1", "target_id": "char_2"
        }

    def test_submit_vote_wrong_phase_rejected(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.submit_vote("char_1", "char_2") is False

    def test_submit_vote_dead_rejected(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        gm.eliminate_player("char_1")
        assert gm.submit_vote("char_1", "char_2") is False

    def test_tally_votes_empty(self, sample_archive):
        gm = GameManager(sample_archive)
        winner, summary, tied = gm.tally_votes()
        assert winner == ""
        assert tied is False
        assert "无投票" in summary

    def test_tally_votes_majority(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        for src, tgt in [("char_1", "char_2"),
                         ("char_2", "char_2"),
                         ("char_3", "char_2"),
                         ("char_4", "char_3")]:
            gm.submit_vote(src, tgt)
        winner, summary, tied = gm.tally_votes()
        assert winner == "char_2"
        assert tied is False
        assert "char_2: 3" in summary

    def test_tally_votes_tied(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        for src, tgt in [("char_1", "char_2"),
                         ("char_2", "char_3"),
                         ("char_3", "char_2"),
                         ("char_4", "char_3")]:
            gm.submit_vote(src, tgt)
        _, _, tied = gm.tally_votes()
        assert tied is True

    def test_check_voting_result_not_enough_votes(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        ended, msg = gm.check_voting_result()
        assert ended is False
        assert "等待" in msg

    def test_check_voting_result_killer_eliminated(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        gm.submit_vote("char_2", "char_1")
        gm.submit_vote("char_3", "char_1")
        gm.submit_vote("char_4", "char_1")
        gm.submit_vote("char_1", "char_2")
        ended, msg = gm.check_voting_result()
        assert ended is True
        assert gm.state.winner == "good"
        assert "Alice" in msg
        assert gm.state.player_states["char_1"].is_alive is False

    def test_check_voting_result_wrong_target(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        gm.submit_vote("char_1", "char_2")
        gm.submit_vote("char_3", "char_2")
        gm.submit_vote("char_4", "char_2")
        gm.submit_vote("char_2", "char_1")
        ended, msg = gm.check_voting_result()
        assert ended is True
        assert gm.state.winner == "killer"
        assert "凶手逃脱" in msg

    def test_check_voting_result_tie_returns_not_ended(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.set_phase(GamePhase.VOTING)
        gm.submit_vote("char_1", "char_2")
        gm.submit_vote("char_2", "char_3")
        gm.submit_vote("char_3", "char_2")
        gm.submit_vote("char_4", "char_3")
        ended, msg = gm.check_voting_result()
        assert ended is False
        assert "平局" in msg

    def test_check_voting_wrong_phase(self, sample_archive):
        gm = GameManager(sample_archive)
        ended, msg = gm.check_voting_result()
        assert ended is False
        assert msg == ""


# ---------- Eliminate player ----------

class TestEliminate:
    def test_eliminate_marks_dead(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.eliminate_player("char_2") is True
        assert gm.state.player_states["char_2"].is_alive is False
        assert gm.state.eliminated_id == "char_2"
        assert "char_2" not in gm.alive_players

    def test_eliminate_unknown_returns_false(self, sample_archive):
        gm = GameManager(sample_archive)
        assert gm.eliminate_player("nope") is False

    def test_eliminate_dead_returns_false(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.eliminate_player("char_2")
        assert gm.eliminate_player("char_2") is False


# ---------- Discussion / summary ----------

class TestDiscussionAndSummary:
    def test_add_discussion(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.add_discussion("char_2", "我觉得 Alice 嫌疑很大")
        assert gm.state.discussion_history == ["Bob: 我觉得 Alice 嫌疑很大"]

    def test_add_discussion_unknown_player_uses_id(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.add_discussion("ghost", "hi")
        assert gm.state.discussion_history == ["ghost: hi"]

    def test_get_game_summary(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.state.winner = "good"
        summary = gm.get_game_summary()
        assert "测试案件" in summary
        assert "好人胜利" in summary
        assert "完整真相" in summary

    def test_force_reveal(self, sample_archive):
        gm = GameManager(sample_archive)
        gm.force_reveal()
        assert gm.current_phase == GamePhase.REVEAL
        assert gm.state.game_ended is True
