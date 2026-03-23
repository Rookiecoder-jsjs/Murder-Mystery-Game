# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Core module for the murder mystery game."""

from app.core.phases import GamePhase
from app.core.config import get_config, AppConfig
from app.core.prompts import PhasePromptTemplates

__all__ = ["GamePhase", "get_config", "AppConfig", "PhasePromptTemplates"]
