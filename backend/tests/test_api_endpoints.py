# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Lightweight guards on endpoint wiring that unit suites elsewhere miss."""

from __future__ import annotations

import inspect

from app.api.endpoints.games import speak_stream
from app.api.schemas import (
    CreateGameRequest,
    DeductionRequest,
    InvestigateRequest,
    LoadGameRequest,
)


def test_speak_stream_declares_game_id_param():
    """Regression guard: speak_stream persists via manager.save(game_id) in
    its stream's finally, and ``game_id`` must therefore be an explicit
    route parameter — otherwise the closure raises NameError and the
    round is never written to disk."""
    params = inspect.signature(speak_stream).parameters
    assert "game_id" in params


def test_quick_mode_api_contract():
    create = CreateGameRequest(topic="速推测试", mode="quick")
    load = LoadGameRequest(story_id="story-1", mode="quick")
    investigate = InvestigateRequest(lead_id="clue-1")

    assert create.mode == "quick"
    assert load.mode == "quick"
    assert investigate.lead_id == "clue-1"


def test_deduction_request_contract():
    request = DeductionRequest(
        target_id="char_1",
        evidence_ids=["clue_a", "clue_b"],
        reason="两条线索在时间线上互相矛盾",
    )

    assert request.target_id == "char_1"
    assert len(request.evidence_ids) == 2
