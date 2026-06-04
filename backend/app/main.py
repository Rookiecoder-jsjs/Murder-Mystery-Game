# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""FastAPI app entry point.

This module is intentionally thin: it only wires the FastAPI app,
middleware, lifespan-managed singletons, and the combined router.

Business logic lives in ``app.services.*``; HTTP shapes in
``app.api.schemas``; route handlers in ``app.api.endpoints.*``.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.logging import configure_logging
from app.services.session_service import (
    InMemorySessionStore,
    JsonFileSessionStore,
    SessionManager,
    SessionStore,
)
from app.services.story_service import (
    StoryService,
    create_m2_client,
    ensure_stories_dir,
)


load_dotenv()


def _cors_origins() -> list[str]:
    """Resolve CORS allowed origins.

    Reads CORS_ALLOWED_ORIGINS env var (comma-separated). When unset or
    "*", returns localhost dev origins only — never a true wildcard in
    combination with allow_credentials=True.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS")
    if not raw or raw.strip() == "*":
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
        ]
    return [o.strip() for o in raw.split(",") if o.strip()]


def _build_session_store() -> SessionStore:
    """Pick persistence backend.

    Set SESSIONS_DIR to enable JSON file persistence (e.g.
    ``SESSIONS_DIR=backend/sessions``); default is in-memory only.
    """
    sessions_dir = os.getenv("SESSIONS_DIR")
    if sessions_dir:
        return JsonFileSessionStore(sessions_dir)
    return InMemorySessionStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    ensure_stories_dir()

    story_service = StoryService()
    m2_client = create_m2_client()
    manager = SessionManager(
        m2_client=m2_client,
        story_service=story_service,
        store=_build_session_store(),
    )
    restored = manager.load_all_persisted()

    app.state.story_service = story_service
    app.state.session_manager = manager

    if restored:
        print(f"[startup] Restored {restored} session(s) from disk")
    yield


app = FastAPI(
    title="剧本杀 API",
    description="剧本杀游戏后端服务 - CAMEL框架版",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict:
    return {"message": "剧本杀 API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    from app.core.port import find_available_port, write_port_file

    port = find_available_port()
    write_port_file(port)
    print(f"后端服务启动于 http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
