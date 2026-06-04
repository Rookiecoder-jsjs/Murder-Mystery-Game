# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Story archive endpoints — list previously generated stories."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_session_manager
from app.services.session_service import SessionManager
from app.services.story_service import list_stories

router = APIRouter(tags=["stories"])


@router.get("/stories")
async def list_available_stories(
    _manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """列出所有可用故事"""
    return {"stories": list_stories()}
