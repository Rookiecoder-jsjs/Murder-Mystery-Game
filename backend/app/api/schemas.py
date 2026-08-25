# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Pydantic request/response schemas for the murder mystery API.

These match the wire format that the React frontend (``frontend/src/api/client.ts``)
expects: ``character_name`` (not character ID) for vote/accuse payloads.
"""

from typing import Optional

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="剧本主题")
    player_name: Optional[str] = Field(None, max_length=50, description="玩家名字")


class LoadGameRequest(BaseModel):
    story_id: str = Field(..., description="故事ID")


class AccuseRequest(BaseModel):
    character_name: str = Field(..., max_length=100, description="被指控的角色名字")


class IntroduceRequest(BaseModel):
    message: Optional[str] = Field("", max_length=500, description="玩家自我介绍")


class SpeakRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="玩家发言内容")


class VoteRequest(BaseModel):
    character_name: str = Field(..., max_length=100, description="投票的角色名字")
