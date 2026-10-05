"""Game lifecycle endpoints — create, load, play actions.

All handlers are ``async`` and every LLM call goes through the session's
async methods (thread-pool offload), so the event loop is never blocked
by a slow model.
"""

from __future__ import annotations

import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import (
    get_session,
    get_session_manager,
    persist_session,
)
from app.api.schemas import (
    AccuseRequest,
    ClueBoardResponse,
    CreateGameRequest,
    IntroduceRequest,
    InvestigateRequest,
    LoadGameRequest,
    SpeakRequest,
    VoteRequest,
)
from app.core.phases import GamePhase
from app.services.session_service import GameSession, SessionManager
from app.services.story_service import StoryService


from app.api.game_route import GameRoute

router = APIRouter(prefix="/games", tags=["games"], route_class=GameRoute)


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
            manager, request.topic, request.mode, request.character_count,
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
    manager: SessionManager, topic: str, mode: str = "classic", character_count: int | None = None
):
    """Run the blocking story generation in a worker thread."""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: manager.create_session(topic=topic, mode=mode, **({"character_count": character_count} if character_count is not None else {})),
    )


@router.post("/load")
async def load_game(
    request: LoadGameRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """加载已有游戏（重新生成 session，故事内容从已存 archive 恢复）"""
    try:
        archive = await asyncio.to_thread(_get_story_service(manager).get_playable_story, request.story_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="剧本尚未完成制作，请从成品库选择其他案件")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="本地剧本读取失败，请稍后重试")
    if not archive:
        raise HTTPException(status_code=404, detail="剧本不存在或存档已损坏")
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


@router.get("/{game_id}/clues", response_model=ClueBoardResponse)
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
    return session.advance_phase()


@router.post("/{game_id}/return-to-investigation")
async def return_to_investigation(
    session: GameSession = Depends(persist_session),
) -> dict:
    return session.return_to_investigation()


@router.post("/{game_id}/start-voting")
async def start_voting(
    session: GameSession = Depends(persist_session),
) -> dict:
    return session.start_voting()


@router.post("/{game_id}/next-investigation-round")
async def next_investigation_round(
    session: GameSession = Depends(persist_session),
) -> dict:
    return session.start_next_round()


@router.post("/{game_id}/ballot-advice")
async def ballot_advice(
    session: GameSession = Depends(persist_session),
) -> dict:
    """Optional opinions use the frozen pre-verdict role contexts."""
    return await session.collect_ballot_advice()


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
    messages = await session.player_speak_collect(request.message, request.target_id, request.presented_clue_ids, request.action_id)
    return {
        "messages": messages,
        "phase": session.game.state.phase,
        "available_actions": session.get_game_status()["available_actions"],
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
    player's question is emitted after it is recorded and saved, so clients
    clear a draft only after acceptance. The final ``done`` event carries the current
    phase; a failure mid-stream is emitted as an ``error`` event.

    Persistence is owned by the session background producer.
    It records and saves every response even after a disconnect.

    """
    session.validate_discussion(request.target_id, request.presented_clue_ids)

    async def event_source():
        try:
            async for msg in session.player_speak_async(request.message, request.target_id, request.presented_clue_ids,
                                                       request.action_id, include_question=True):
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
    result = await session.vote_async(request.character_name)
    if result["game_ended"]:
        return {**result, "reveal": session.get_reveal_info()}
    return result
