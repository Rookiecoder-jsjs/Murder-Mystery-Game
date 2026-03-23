# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Configuration management for the murder mystery game."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class ModelConfig:
    """Model configuration."""

    api_key: str
    base_url: str
    model_name: str


@dataclass
class DeepSeekConfig:
    """DeepSeek model configuration for story generation."""

    api_key: str
    base_url: str
    model_name: str = "deepseek-reasoner"

    @classmethod
    def from_env(cls) -> "DeepSeekConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner"),
        )


@dataclass
class MiniMaxConfig:
    """MiniMax M2-her model configuration for role-playing."""

    api_key: str
    base_url: str
    model_name: str = "M2-her"

    @classmethod
    def from_env(cls) -> "MiniMaxConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("MINIMAX_API_KEY", ""),
            base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
            model_name=os.getenv("MINIMAX_MODEL", "M2-her"),
        )


@dataclass
class AppConfig:
    """Application configuration."""

    deepseek: DeepSeekConfig
    minimax: MiniMaxConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create config from environment variables."""
        return cls(
            deepseek=DeepSeekConfig.from_env(),
            minimax=MiniMaxConfig.from_env(),
        )


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance.

    Returns:
        The application configuration.
    """
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from environment variables.

    Returns:
        The reloaded application configuration.
    """
    global _config
    _config = AppConfig.from_env()
    return _config
