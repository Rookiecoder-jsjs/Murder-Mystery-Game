# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Pydantic request/response schemas for the murder mystery API.

These match the wire format that the React frontend (``frontend/src/api/client.ts``)
expects: ``character_name`` (not character ID) for vote/accuse payloads.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="剧本主题")
    character_count: int | None = Field(None, strict=True, ge=3, le=8, description="角色人数（含玩家，不含受害者）；空为自动")
    player_name: Optional[str] = Field(None, max_length=50, description="玩家名字")
    mode: Literal["classic", "quick"] = Field("classic", description="游戏模式")


class LoadGameRequest(BaseModel):
    story_id: str = Field(..., description="故事ID")
    mode: Literal["classic", "quick"] = Field("classic", description="游戏模式")


class InvestigateRequest(BaseModel):
    lead_id: Optional[str] = Field(None, max_length=100, description="调查方向")


class AccuseRequest(BaseModel):
    character_name: str = Field(..., max_length=100, description="被指控的角色名字")


class IntroduceRequest(BaseModel):
    message: Optional[str] = Field("", max_length=500, description="玩家自我介绍")


class SpeakRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="玩家发言内容")
    target_id: Optional[str] = Field(None, max_length=100, description="定向询问角色；缺省为全员讨论")
    presented_clue_ids: list[str] = Field(default_factory=list, max_length=15, description="出示的已知证据")
    action_id: Optional[str] = Field(None, pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", description="本次问题的提交标识")


class VoteRequest(BaseModel):
    character_name: str = Field(..., max_length=100, description="投票的角色名字")


class ClueInfo(BaseModel):
    id: str
    title: str = Field('', description="可见线索的调查名称；旧剧本可能为空")
    content: str
    type: Literal['physical', 'testimony', 'document']
    holder_name: str
    is_revealed: bool


class ClueBoardResponse(BaseModel):
    clues: list[ClueInfo]
    scene_public_clues: list[ClueInfo]
    accusation_points: int


class ImportStoryRequest(BaseModel):
    package: dict
