# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""FastAPI dependency providers.

The ``SessionManager`` is a singleton created in the FastAPI ``lifespan``
handler and attached to ``app.state``. Endpoints retrieve it via
``Depends(get_session_manager)``, which gives us:
- testability (override the dependency in tests)
- no global mutable state
- one obvious place to wire shared resources
"""

from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, Request

from app.services.session_service import GameSession, SessionManager


def get_session_manager(request: Request) -> SessionManager:
    """Return the SessionManager singleton from app state."""
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="SessionManager 未初始化")
    return manager


def get_session(
    game_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> GameSession:
    """Return the GameSession for the given path parameter.

    FastAPI's path-param injection happens before ``Depends`` evaluation,
    so ``game_id`` is filled in by the time this runs.
    """
    return manager.get(game_id)


def persist_session(
    game_id: str,
    session: GameSession = Depends(get_session),
    manager: SessionManager = Depends(get_session_manager),
) -> Iterator[GameSession]:
    """Yield the session, then persist after the response is sent.

    Use this on mutating endpoints: ``def endpoint(s: GameSession = Depends(persist_session))``.
    No-op for ``InMemorySessionStore``; writes JSON for ``JsonFileSessionStore``.
    """
    try:
        yield session
    finally:
        # Persist under the registry key (game_id), not the story id.
        manager.save(game_id)
