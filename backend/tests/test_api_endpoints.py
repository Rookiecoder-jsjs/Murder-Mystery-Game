# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Lightweight guards on endpoint wiring that unit suites elsewhere miss."""

from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi import HTTPException
from app.core.errors import GameError

from app.api.endpoints.games import (
    advance_phase,
    return_to_investigation,
    next_investigation_round,
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
            if session.get_investigation_options():
                session.investigate()
            await advance_phase(session=session)  # -> discussion
            await session.player_speak_collect("本轮推论")
            assert session.game.state.phase == "discussion"
            assert session.game.state.round == expected_round

            # 未完成全部调查轮次前，进入投票必须被拒
            with pytest.raises((HTTPException, GameError)) as exc:
                await start_voting(session=session)
            assert exc.value.status_code == 400

            await next_investigation_round(session=session)  # explicit round+1
            assert session.game.state.phase == "investigation"
            assert session.game.state.round == expected_round + 1

        if session.get_investigation_options():
            session.investigate()
        await advance_phase(session=session)  # 第 3 轮搜证后进入讨论
        await session.player_speak_collect("最终推论")
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
        with pytest.raises((HTTPException, GameError)) as exc:
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


def test_reveal_is_not_available_before_game_ends(sample_archive):
    from app.api.endpoints.games import reveal
    session = _quick_session(sample_archive)
    with pytest.raises((HTTPException, GameError)) as exc:
        asyncio.run(reveal(session=session))
    assert exc.value.status_code == 400


def test_next_phase_cannot_skip_the_vote(sample_archive):
    session = _quick_session(sample_archive)
    session.game.set_phase(GamePhase.VOTING)
    with pytest.raises((HTTPException, GameError)):
        asyncio.run(advance_phase(session=session))
    assert session.game.current_phase == GamePhase.VOTING
    assert session.game.state.winner is None


def test_empty_quick_round_does_not_advance(sample_archive):
    session = _quick_session(sample_archive)
    session.game.set_phase(GamePhase.INVESTIGATION)
    with pytest.raises((HTTPException, GameError)):
        asyncio.run(advance_phase(session=session))
    session.game.set_phase(GamePhase.DISCUSSION)
    asyncio.run(return_to_investigation(session=session))
    assert session.game.state.round == 1


def test_final_round_allows_more_investigation(sample_archive):
    session = _quick_session(sample_archive)
    session.game.state.round = 3
    session.game.set_phase(GamePhase.DISCUSSION)
    asyncio.run(return_to_investigation(session=session))
    assert session.game.state.phase == "investigation"
    assert session.game.state.round == 3
    assert session.get_investigation_options()


def test_voting_requires_discussion_in_final_round(sample_archive):
    session = _quick_session(sample_archive)
    session.game.state.round = 3
    session.game.set_phase(GamePhase.DISCUSSION)
    session.investigate()
    with pytest.raises((HTTPException, GameError)):
        asyncio.run(start_voting(session=session))


def test_quick_mode_exhausted_evidence_still_reaches_voting(sample_archive):
    session = _quick_session(sample_archive)
    for player in session.game.state.player_states.values():
        player.known_clues = [clue.id for clue in session.archive.clues]
    session.game.set_phase(GamePhase.INVESTIGATION)
    async def run():
        for round_number in (1, 2, 3):
            await advance_phase(session=session)
            await session.player_speak_collect("核对已知证据")
            if round_number < 3:
                await next_investigation_round(session=session)
        await start_voting(session=session)
    asyncio.run(run())
    assert session.game.current_phase == GamePhase.VOTING


def test_quick_revote_and_final_round_progress_survive_restart(sample_archive):
    session = _quick_session(sample_archive)
    session.game.state.round = 3
    session.game.set_phase(GamePhase.DISCUSSION)
    session.investigate()
    asyncio.run(session.player_speak_collect("最终推论"))
    restored = GameSession.from_snapshot(session.to_snapshot("game"), sample_archive, StubRoleplayClient())
    asyncio.run(start_voting(session=restored))
    for source, target in [("char_1", "char_2"), ("char_2", "char_1"),
                           ("char_3", "char_2"), ("char_4", "char_1")]:
        restored.game.submit_vote(source, target)
    assert not restored.game.check_voting_result()[0]
    asyncio.run(return_to_investigation(session=restored))
    assert restored.game.state.round == 3
    assert not restored.game.get_votes()
    asyncio.run(advance_phase(session=restored))
    asyncio.run(start_voting(session=restored))
    assert restored.game.current_phase == GamePhase.VOTING


def test_http_role_script_evidence_question_and_single_player_verdict(sample_archive):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.endpoints.games import router
    from app.services.session_service import SessionManager
    app = FastAPI()
    app.include_router(router)
    manager = SessionManager(StubRoleplayClient(), None)
    gid, session = manager.create_session(archive=sample_archive)
    app.state.session_manager = manager
    client = TestClient(app)
    status = client.get(f'/games/{gid}').json()
    assert status['player']['role_script']
    assert all('role_script' not in c for c in status['characters'])
    assert client.get(f'/games/{gid}/reveal').status_code == 400
    session.game.set_phase(GamePhase.DISCUSSION)
    target = next(iter(session.ai_characters))
    clue = session.game.get_player_clues(session.human_player_id)[0]
    response = client.post(f'/games/{gid}/speak', json={
        'message': '请解释这条证据。', 'target_id': target,
        'presented_clue_ids': [clue.id],
    })
    assert response.status_code == 200
    assert len(response.json()['messages']) == 1
    assert clue.id in {c['id'] for c in client.get(f'/games/{gid}/clues').json()['scene_public_clues']}
    session.start_voting()
    response = client.post(f'/games/{gid}/vote', json={'character_name': 'Alice'})
    assert response.status_code == 200
    assert response.json()['winner'] == 'good'
    assert response.json()['reveal']['votes']


def test_local_archive_error_runs_off_event_loop_and_does_not_leak_solution(sample_archive):
    import threading
    from types import SimpleNamespace
    from app.api.endpoints.games import load_game
    main_thread = threading.get_ident()
    calls = []
    def rejected_review(_):
        calls.append(threading.get_ident())
        raise ValueError('真凶是绝不可提前展示的人物')
    manager = SimpleNamespace(_story_service=SimpleNamespace(get_playable_story=rejected_review))
    with pytest.raises((HTTPException, GameError)) as exc:
        asyncio.run(load_game(LoadGameRequest(story_id=sample_archive.id), manager))
    assert exc.value.status_code == 422
    assert '真凶' not in exc.value.detail
    assert calls and calls[0] != main_thread
