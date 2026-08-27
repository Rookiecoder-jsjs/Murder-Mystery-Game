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
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import ENV_FILE, validate_secrets
from app.core.logging import configure_logging
from app.services.session_service import (
    InMemorySessionStore,
    JsonFileSessionStore,
    SessionManager,
    SessionStore,
)
from app.services.story_service import (
    StoryService,
    create_roleplay_client,
    ensure_stories_dir,
)
from app.services.image_service import PORTRAITS_DIR, ensure_portraits_dir


load_dotenv(ENV_FILE)
ensure_portraits_dir()

# backend/ 目录的绝对路径（config.py 从 app/core/config.py 向上三级解析
# 得到 backend/，这里用同一方式取 backend/，供相对 SESSIONS_DIR 解析）。
_BACKEND_DIR = Path(__file__).resolve().parent.parent


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

    Set SESSIONS_DIR to enable JSON file persistence (e.g. ``sessions``);
    default is in-memory only. A relative path is resolved against the
    backend/ directory so it works regardless of the process CWD.
    """
    sessions_dir = os.getenv("SESSIONS_DIR")
    if not sessions_dir:
        return InMemorySessionStore()
    path = Path(sessions_dir)
    if not path.is_absolute():
        path = _BACKEND_DIR / path
    return JsonFileSessionStore(str(path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    validate_secrets()  # 密钥缺失时快速失败，给出可读错误而非冷门 401
    ensure_stories_dir()

    story_service = StoryService()
    roleplay_client = create_roleplay_client()
    manager = SessionManager(
        roleplay_client=roleplay_client,
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
    description="剧本杀游戏后端服务 - OpenAI 兼容大模型 API 版",
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

app.mount(
    "/assets/portraits",
    StaticFiles(directory=str(PORTRAITS_DIR)),
    name="portraits",
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
