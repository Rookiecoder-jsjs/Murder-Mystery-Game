# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Configuration management for the murder mystery game."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 环境变量文件固定锚定在 backend/.env（相对此文件解析，不依赖进程 CWD）。
# 真实密钥只存这里（已被 .gitignore 忽略）；模板与注释见 backend/.env.simple。
ENV_FILE: Path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)

# 启动必需的环境变量 —— 缺失时直接拒绝启动（见 validate_secrets）
REQUIRED_SECRETS: tuple[str, ...] = ("DEEPSEEK_API_KEY",)


def validate_secrets() -> None:
    """Fail fast when required secrets are missing at startup.

    Called by ``main.py`` lifespan so a misconfigured deployment fails
    with a clear message instead of an obscure 401 from the LLM provider.
    """
    missing = [name for name in REQUIRED_SECRETS if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(
            "缺少必需的环境变量："
            + "、".join(missing)
            + "。请在 backend/.env 中配置（可从 backend/.env.simple 复制模板）。"
        )


@dataclass
class ModelConfig:
    """Model configuration."""

    api_key: str
    base_url: str
    model_name: str


@dataclass
class GenerationParams:
    """LLM generation parameters."""

    temperature: float = 1.0
    top_p: float = 0.95
    max_completion_tokens: int = 2048


def _env_float(name: str, default: float) -> float:
    """Read a float from env, falling back to default on parse error."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    """Read an int from env, falling back to default on parse error."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Read a bool from env ("1"/"true"/"yes" are truthy, case-insensitive)."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class DeepSeekConfig:
    """DeepSeek model configuration for story generation (thinking mode on)."""

    api_key: str
    base_url: str
    model_name: str = "deepseek-v4-pro"

    @classmethod
    def from_env(cls) -> "DeepSeekConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        )


@dataclass
class RoleplayConfig:
    """Roleplay (character) model configuration.

    Defaults to the fast DeepSeek variant with thinking mode disabled —
    chat-style roleplay wants low latency, not deep reasoning.
    """

    api_key: str
    base_url: str
    model_name: str = "deepseek-v4-flash"
    generation: GenerationParams = field(default_factory=GenerationParams)
    thinking_enabled: bool = False

    @classmethod
    def from_env(cls) -> "RoleplayConfig":
        """Create config from environment variables.

        Falls back to DEEPSEEK_API_KEY when no separate roleplay key is set —
        both roles usually share the same DeepSeek account.
        """
        return cls(
            api_key=os.getenv("ROLEPLAY_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv(
                "ROLEPLAY_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            ),
            model_name=os.getenv("ROLEPLAY_MODEL", "deepseek-v4-flash"),
            generation=GenerationParams(
                temperature=_env_float("ROLEPLAY_TEMPERATURE", 1.0),
                top_p=_env_float("ROLEPLAY_TOP_P", 0.95),
                max_completion_tokens=_env_int("ROLEPLAY_MAX_TOKENS", 2048),
            ),
            thinking_enabled=_env_bool("ROLEPLAY_THINKING_ENABLED", False),
        )


@dataclass
class AppConfig:
    """Application configuration."""

    deepseek: DeepSeekConfig
    roleplay: RoleplayConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create config from environment variables."""
        return cls(
            deepseek=DeepSeekConfig.from_env(),
            roleplay=RoleplayConfig.from_env(),
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
