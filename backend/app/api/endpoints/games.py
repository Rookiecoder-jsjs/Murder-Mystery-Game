# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game lifecycle endpoints — create, load, play actions."""

from __future__ import annotations

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
    LoadGameRequest,
    SpeakRequest,
    VoteRequest,
)
from app.core.phases import GamePhase
from app.services.session_service import GameSession, SessionManager
from app.services.story_service import StoryService


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
        game_id, session = manager.create_session(topic=request.topic)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建游戏失败: {e}")

    return {
        "game_id": game_id,
        "story_id": session.archive.id,
        "topic": request.topic,
        "phase": session.game.state.phase,
        "player": session.get_player_info(),
        "characters": session.get_all_characters(),
    }


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
        game_id, session = manager.create_session(archive=archive)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "game_id": game_id,
        "story_id": session.archive.id,
        "phase": session.game.state.phase,
        "player": session.get_player_info(),
        "characters": session.get_all_characters(),
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
    return {"history": session.game.state.discussion_history}


# ---------------------------------------------------------------------------
# Phase / turn actions
# ---------------------------------------------------------------------------


@router.post("/{game_id}/introduce")
async def player_introduce(
    game_id: str,
    message: str = "",
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.INTRODUCTION.value:
        raise HTTPException(status_code=400, detail="当前不是自我介绍阶段")
    return session.player_introduce(message)


@router.post("/{game_id}/next-phase")
async def advance_phase(
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase == GamePhase.DISCUSSION.value:
        if session.game.state.round >= session.game.state.max_rounds:
            session.game.next_phase()
        else:
            session.game.state.round += 1
    else:
        session.game.next_phase()
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
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

    session.game.set_phase(GamePhase.INVESTIGATION)
    session.game.state.discussion_history = []
    session.game.distribute_random_clues(session.human_player_id, 1)
    for char_id in session.ai_characters:
        session.game.distribute_random_clues(char_id, 1)
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
    }


@router.post("/{game_id}/start-voting")
async def start_voting(
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")
    session.game.set_phase(GamePhase.VOTING)
    session.game.state.turn = 0
    return {
        "phase": session.game.state.phase,
        "round": session.game.state.round,
    }


# ---------------------------------------------------------------------------
# Player actions
# ---------------------------------------------------------------------------


@router.post("/{game_id}/speak")
async def speak(
    request: SpeakRequest,
    session: GameSession = Depends(persist_session),
) -> dict:
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")
    return {
        "messages": session.player_speak(request.message),
        "phase": session.game.state.phase,
    }


@router.post("/{game_id}/speak/stream")
async def speak_stream(
    request: SpeakRequest,
    session: GameSession = Depends(persist_session),
) -> StreamingResponse:
    """SSE variant of ``/speak``.

    Emits one ``message`` event per AI response as it completes (the
    human player's message is the first event). The final ``done`` event
    carries the current phase. A failed response is emitted as an
    ``error`` event instead of being swallowed.
    """
    if session.game.state.phase != GamePhase.DISCUSSION.value:
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")

    import json

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
    result = session.vote(request.character_name)
    if result["game_ended"]:
        return {**result, "reveal": session.get_reveal_info()}
    return {
        "votes": result.get("votes", {}),
        "result": result.get("result", ""),
        "game_ended": False,
        "winner": None,
        "phase": session.game.state.phase,
    }
