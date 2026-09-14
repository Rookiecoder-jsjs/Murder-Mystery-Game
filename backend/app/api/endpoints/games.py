# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game lifecycle endpoints — create, load, play actions.

All handlers are ``async`` and every LLM call goes through the session's
async methods (thread-pool offload), so the event loop is never blocked
by a slow model.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import (
    get_session,
    get_session_manager,
    persist_session,
)
from app.api.schemas import (
    AccuseRequest,
    CreateGameRequest,
    IntroduceRequest,
    InvestigateRequest,
    LoadGameRequest,
    SpeakRequest,
    VoteRequest,
)
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.services.session_service import GameSession, SessionManager
from app.services.story_service import StoryService


logger = get_logger(__name__)


router = APIRouter(prefix="/games", tags=["games"])


def _get_story_service(manager: SessionManager) -> StoryService:
    """Reach into the SessionManager for its story_service collaborator."""
    return manager._story_service  # internal but stable for this file


# ---------------------------------------------------------------------------
# Session creation / loading
# ---------------------------------------------------------------------------


@router.post("")
async def create_game(
    request: CreateGameRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """创建新游戏"""
    try:
        game_id, session = await _create_in_thread(
            manager, request.topic, request.mode,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建游戏失败: {e}")

    return {
        "game_id": game_id,
        "story_id": session.archive.id,
        "topic": request.topic,
        "phase": session.game.state.phase,
        "mode": session.game.state.mode,
        "max_rounds": session.game.state.max_rounds,
        "player": session.get_player_info(),
        "characters": session.get_all_characters(),
        "case_brief": session.get_case_brief(),
    }


async def _create_in_thread(
    manager: SessionManager, topic: str, mode: str = "classic"
):
    """Run the blocking story generation in a worker thread."""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: manager.create_session(topic=topic, mode=mode),
    )


@router.post("/load")
async def load_game(
    request: LoadGameRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """加载已有游戏（重新生成 session，故事内容从已存 archive 恢复）"""
    archive = _get_story_service(manager).get_story(request.story_id)
    if not archive:
        raise HTTPException(status_code=404, detail="故事不存在")
    try:
        game_id, session = manager.create_session(
            archive=archive, mode=request.mode,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "game_id": game_id,
        "story_id": session.archive.id,
        "phase": session.game.state.phase,
        "mode": session.game.state.mode,
        "max_rounds": session.game.state.max_rounds,
        "player": session.get_player_info(),
        "characters": session.get_all_characters(),
        "case_brief": session.get_case_brief(),
    }


# ---------------------------------------------------------------------------
# Read-only views
# ---------------------------------------------------------------------------


@router.get("/{game_id}")
async def get_game_status(
    session: GameSession = Depends(get_session),
) -> dict:
    return session.get_game_status()


@router.get("/{game_id}/clues")
async def get_clues(
    session: GameSession = Depends(get_session),
) -> dict:
    return session.get_clue_board()


@router.get("/{game_id}/reveal")
async def reveal(
    session: GameSession = Depends(get_session),
) -> dict:
    return session.get_reveal_info()


@router.get("/{game_id}/discussion-history")
async def get_discussion_history(
    session: GameSession = Depends(get_session),
) -> dict:
    return {"history": session.get_discussion_history()}


# ---------------------------------------------------------------------------
# Phase / turn actions
# ---------------------------------------------------------------------------


@router.post("/{game_id}/introduce")
async def player_introduce(
    request: IntroduceRequest,
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.INTRODUCTION.value:
        raise HTTPException(status_code=400, detail="当前不是自我介绍阶段")
    return await session.player_introduce_async(request.message or "")


@router.post("/{game_id}/next-phase")
async def advance_phase(
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase == GamePhase.DISCUSSION.value:
        if session.game.state.mode == "quick":
            # 速推模式的讨论阶段由「返回搜证」「进入投票」驱动；
            # 走这里的经典逻辑会误加调查轮计数
            raise HTTPException(
                status_code=400,
                detail="速推模式请使用「返回搜证」或「进入投票」推进",
            )
        if session.game.state.round >= session.game.state.max_rounds:
            session.game.next_phase()
        else:
            session.game.state.round += 1
    else:
        session.game.next_phase()
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
        "investigation_options": session.get_investigation_options(),
        "last_event": session.game.state.last_event,
    }


@router.post("/{game_id}/return-to-investigation")
async def return_to_investigation(
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase not in [
        GamePhase.DISCUSSION.value,
        GamePhase.VOTING.value,
    ]:
        raise HTTPException(status_code=400, detail="只能在讨论或投票阶段返回搜证")

    was_revote = (
        session.game.state.phase == GamePhase.VOTING.value
        and bool(session.game.get_votes())
    )

    if (
        session.game.state.mode == "quick"
        and session.game.state.phase == GamePhase.DISCUSSION.value
    ):
        if session.game.state.round >= session.game.state.max_rounds:
            raise HTTPException(
                status_code=400,
                detail="速推模式已完成调查轮次，请进入投票",
            )
        session.game.state.round += 1

    session.game.set_phase(GamePhase.INVESTIGATION)
    # Discussion history survives — it is each side's memory of the case.
    # A fresh voting round after this needs clean ballots.
    if was_revote:
        session.game.reset_votes()
    quick_mode = session.game.state.mode == "quick"
    if not quick_mode:
        session.game.distribute_random_clues(session.human_player_id, 1)
    for char_id in session.ai_characters:
        # 速推模式：场景线索留给玩家当调查方向，AI 只抽人物持有的线索
        session.game.distribute_random_clues(
            char_id, 1, exclude_scene=quick_mode,
        )
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
        "investigation_options": session.get_investigation_options(),
        "last_event": session.game.state.last_event,
    }


@router.post("/{game_id}/start-voting")
async def start_voting(
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")
    if (
        session.game.state.mode == "quick"
        and session.game.state.round < session.game.state.max_rounds
    ):
        raise HTTPException(
            status_code=400,
            detail=f"请完成第 {session.game.state.round + 1} 轮调查后再进入投票",
        )
    session.game.set_phase(GamePhase.VOTING)
    session.game.reset_votes()
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
        "investigation_options": session.get_investigation_options(),
        "last_event": session.game.state.last_event,
    }


# ---------------------------------------------------------------------------
# Player actions
# ---------------------------------------------------------------------------


@router.post("/{game_id}/investigate")
async def investigate(
    request: InvestigateRequest | None = None,
    session: GameSession = Depends(persist_session),
) -> dict:
    """主动搜证；速推模式支持选择调查方向。"""
    return session.investigate(request.lead_id if request else None)


@router.post("/{game_id}/speak")
async def speak(
    request: SpeakRequest,
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")
    messages = await session.player_speak_collect(request.message)
    return {
        "messages": messages,
        "phase": session.game.state.phase,
    }


@router.post("/{game_id}/speak/stream")
async def speak_stream(
    game_id: str,
    request: SpeakRequest,
    session: GameSession = Depends(get_session),
    manager: SessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    """SSE variant of ``/speak``.

    Emits one ``message`` event per AI response as it completes. The
    human player's own message is NOT re-emitted — the frontend echoes
    it optimistically. The final ``done`` event carries the current
    phase; a failure mid-stream is emitted as an ``error`` event.

    Persistence happens after the body is consumed (this handler uses
    ``get_session``, not ``persist_session``): the stream mutates state
    while it runs, so a snapshot taken before the first AI reply would
    drop the entire round.
    """
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")

    async def event_source():
        try:
            async for msg in session.player_speak_async(request.message):
                payload = json.dumps(msg, ensure_ascii=False)
                yield f"event: message\ndata: {payload}\n\n"
            terminal = json.dumps(
                {"phase": session.game.state.phase}, ensure_ascii=False,
            )
            yield f"event: done\ndata: {terminal}\n\n"
        except Exception as e:
            err = json.dumps({"detail": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n"
        finally:
            # Stream is fully consumed (success, error, or disconnect):
            # snapshot now so the round's entries + AI memories persist.
            try:
                manager.save(game_id)
            except Exception as e:
                logger.warning("流式发言后保存会话失败: %s", e)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{game_id}/accuse")
async def accuse(
    request: AccuseRequest,
    session: GameSession = Depends(persist_session),
) -> dict:
    result = session.accuse(request.character_name)
    if result["game_ended"]:
        return {**result, "reveal": session.get_reveal_info()}
    return result


@router.post("/{game_id}/vote")
async def vote(
    request: VoteRequest,
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.VOTING.value:
        raise HTTPException(status_code=400, detail="当前不是投票阶段")
    result = await session.vote_async(request.character_name)
    if result["game_ended"]:
        return {**result, "reveal": session.get_reveal_info()}
    return result
