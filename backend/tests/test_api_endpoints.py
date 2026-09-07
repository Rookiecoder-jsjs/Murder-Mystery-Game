# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Lightweight guards on endpoint wiring that unit suites elsewhere miss."""

from __future__ import annotations

import inspect

from app.api.endpoints.games import speak_stream


def test_speak_stream_declares_game_id_param():
    """Regression guard: speak_stream persists via manager.save(game_id) in
    its stream's finally, and ``game_id`` must therefore be an explicit
    route parameter — otherwise the closure raises NameError and the
    round is never written to disk."""
    params = inspect.signature(speak_stream).parameters
    assert "game_id" in params
