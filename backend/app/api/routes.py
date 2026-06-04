# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Top-level API router — combines all endpoint modules."""

from fastapi import APIRouter

from app.api.endpoints import games, stories


router = APIRouter()
router.include_router(games.router)
router.include_router(stories.router)
