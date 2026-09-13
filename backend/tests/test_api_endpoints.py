# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Lightweight guards on endpoint wiring that unit suites elsewhere miss."""

from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from app.api.endpoints.games import (
    advance_phase,
    return_to_investigation,
    speak_stream,
    start_voting,
)
from app.api.schemas import CreateGameRequest, InvestigateRequest, LoadGameRequest
from app.core.phases import GamePhase
from app.domain.models import CaseData, ClueData, ScriptCharacter, StoryArchive
from app.services.session_service import GameSession
from tests.test_session_service import StubRoleplayClient


def test_speak_stream_declares_game_id_param():
    """Regression guard: speak_stream persists via manager.save(game_id) in
    its stream's finally, and ``game_id`` must therefore be an explicit
    route parameter — otherwise the closure raises NameError and the
    round is never written to disk."""
    params = inspect.signature(speak_stream).parameters
    assert "game_id" in params


def test_quick_mode_api_contract():
    create = CreateGameRequest(topic="速推测试", mode="quick")
    load = LoadGameRequest(story_id="story-1", mode="quick")
    investigate = InvestigateRequest(lead_id="clue-1")

    assert create.mode == "quick"
    assert load.mode == "quick"
    assert investigate.lead_id == "clue-1"


# ---------- quick-mode round cycle (regression: voting deadlock) ----------


def _quick_session(sample_archive):
    return GameSession(
        sample_archive, "char_2", StubRoleplayClient(), mode="quick",
    )


def test_quick_mode_round_cycle_reaches_voting(sample_archive):
    """完整轮次循环：搜证 → 讨论 → 返回搜证 ×2 → 投票解锁。

    回归保护：进入讨论时 round 被清零曾导致 start_voting
    永远 400（速推模式无法进入投票的死锁）。
    """
    session = _quick_session(sample_archive)
    session.game.set_phase(GamePhase.INVESTIGATION)

    async def run():
        for expected_round in (1, 2):
            await advance_phase(session=session)  # -> discussion
            assert session.game.state.phase == "discussion"
            assert session.game.state.round == expected_round

            # 未完成全部调查轮次前，进入投票必须被拒
            with pytest.raises(HTTPException) as exc:
                await start_voting(session=session)
            assert exc.value.status_code == 400

            await return_to_investigation(session=session)  # -> round+1
            assert session.game.state.phase == "investigation"
            assert session.game.state.round == expected_round + 1

        await advance_phase(session=session)  # 第 3 轮搜证后进入讨论
        assert session.game.state.round == 3

        await start_voting(session=session)  # 投票解锁，不再 400
        assert session.game.state.phase == "voting"

    asyncio.run(run())


def test_quick_mode_next_phase_in_discussion_rejected(sample_archive):
    """速推模式讨论阶段不接受 next-phase（会误加调查轮计数），
    前端应走「返回搜证」/「进入投票」。"""
    session = _quick_session(sample_archive)
    session.game.set_phase(GamePhase.DISCUSSION)

    async def run():
        with pytest.raises(HTTPException) as exc:
            await advance_phase(session=session)
        assert exc.value.status_code == 400

    asyncio.run(run())


def _scene_only_archive() -> StoryArchive:
    """唯一可用线索是场景线索的极简档案——抽或不抽完全确定，
    消除随机翻车面（旧写法 (4/5)^3 ≈ 51% 概率放行坏代码）。"""
    return StoryArchive(
        id="story-scene-only",
        created_at="2026-01-01 00:00:00",
        topic="速推",
        title="密室",
        case=CaseData(
            title="密室", background="b", victim="v",
            crime="c", true_killer="char_h", motive="m",
        ),
        characters=[
            ScriptCharacter(
                id="char_h", name="甲",
                public_identity="侦探", secret="s",
            ),
            ScriptCharacter(
                id="char_ai", name="乙",
                public_identity="医生", secret="s",
            ),
        ],
        clues=[
            ClueData(
                id="clue_scene", content="现场的脚印", type="physical",
                holder_id="scene", reveal_to_all=False,
            ),
        ],
        story_content="真相",
    )


def _assert_scene_reserved(session: GameSession, lead_ids: list[str]) -> None:
    scene = session.archive.clues[0]
    assert scene.reveal_to_all is False
    assert all(
        "clue_scene" not in ps.known_clues
        for ps in session.game.state.player_states.values()
    )
    assert [o["id"] for o in session.get_investigation_options()] == lead_ids


def test_quick_mode_initial_draws_reserve_scene_clues():
    """速推开局：玩家与 AI 的随机开局抽取都不得碰场景线索——否则
    开局即公开一条调查方向并把它泄露进所有 AI 的上下文。"""
    session = GameSession(
        _scene_only_archive(), "char_h", StubRoleplayClient(), mode="quick",
    )
    session.game.set_phase(GamePhase.INVESTIGATION)

    _assert_scene_reserved(session, ["clue_scene"])


def test_quick_mode_ai_draws_reserve_scene_clues():
    """速推返回搜证：AI 抽取不碰场景线索（唯一可用就是场景线索，
    抽与不抽完全确定）。"""
    session = GameSession(
        _scene_only_archive(), "char_h", StubRoleplayClient(), mode="quick",
    )
    session.game.set_phase(GamePhase.DISCUSSION)
    leads = [o["id"] for o in session.get_investigation_options()]

    asyncio.run(return_to_investigation(session=session))

    _assert_scene_reserved(session, leads)


def test_classic_mode_draws_may_claim_scene_clues():
    """经典模式维持原行为：返回搜证的随机抽取不保留场景线索。"""
    session = GameSession(_scene_only_archive(), "char_h", StubRoleplayClient())
    scene = session.archive.clues[0]
    # 复位构造期随机抽取的影响，隔离被测路径
    scene.reveal_to_all = False
    for ps in session.game.state.player_states.values():
        ps.known_clues = [c for c in ps.known_clues if c != "clue_scene"]
    session.game.set_phase(GamePhase.DISCUSSION)

    asyncio.run(return_to_investigation(session=session))

    # 经典模式人类随机抽取面向全池——池中唯一线索必被认领并公开
    assert scene.reveal_to_all is True
