# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""API schemas using Pydantic."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    """Request to create a new game."""

    topic: str = Field(..., description="The story topic/theme")
    character_id: str = Field(..., description="The character ID the player will control")
    show_reasoning: bool = Field(
        default=False,
        description="Whether to show DeepSeek reasoning",
    )


class GameStatusResponse(BaseModel):
    """Game status response."""

    session_id: str
    story_id: str
    title: str
    phase: str
    round: int
    game_ended: bool
    winner: Optional[str] = None
    human_player_id: str


class CharacterResponse(BaseModel):
    """Character information."""

    id: str
    name: str
    public_identity: str
    is_killer: bool
    appearance: str
    dialogue_style: str


class ClueResponse(BaseModel):
    """Clue information."""

    id: str
    content: str
    type: str
    holder_id: str
    status: str


class ClueBoardResponse(BaseModel):
    """Clue board response."""

    owned: List[ClueResponse]
    available: List[ClueResponse]
    scene_public: List[ClueResponse]


class SpeakRequest(BaseModel):
    """Request to speak in discussion."""

    message: str = Field(..., description="The message to speak")


class DiscussionResponse(BaseModel):
    """Discussion response."""

    player_message: str
    character_responses: Dict[str, str]
    discussion_history: List[str]


class VoteRequest(BaseModel):
    """Request to vote."""

    target_id: str = Field(..., description="The character ID to vote for")


class VoteResponse(BaseModel):
    """Vote response."""

    votes: Dict[str, str]
    result: Optional[str] = None
    game_ended: bool = False


class AccuseRequest(BaseModel):
    """Request to accuse."""

    target_id: str = Field(..., description="The character ID to accuse")


class AccuseResponse(BaseModel):
    """Accuse response."""

    is_correct: bool
    result: str
    game_ended: bool = True


class RevealResponse(BaseModel):
    """Reveal response."""

    summary: str
    story_content: str
    winner: str


class GameCreateResponse(BaseModel):
    """Response after creating a game."""

    session_id: str
    story_id: str
    title: str
    human_player: CharacterResponse
    characters: List[CharacterResponse]
    phase: str
