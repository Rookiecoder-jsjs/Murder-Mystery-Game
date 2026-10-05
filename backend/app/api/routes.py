"""Top-level API router — combines all endpoint modules."""

from fastapi import APIRouter

from app.api.endpoints import games, stories


router = APIRouter()
router.include_router(games.router)
router.include_router(stories.router)
