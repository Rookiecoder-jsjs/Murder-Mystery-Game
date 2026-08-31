"""Structured JSONL tracing of LLM chat calls for troubleshooting.

Every completed (or failed) chat-completion call is appended as one JSON
object to a per-day JSONL file (``backend/logs/llm/YYYY-MM-DD.jsonl`` by
default). A record captures the full request (model, messages), the
response (content, reasoning/thinking when present, usage, latency) and
enough game context to relocate the call later. Env knobs:

- ``LLM_TRACE_ENABLED``       (default 1)       master switch
- ``LLM_TRACE_DIR``           (default backend/logs/llm)  output directory
- ``LLM_TRACE_MAX_BODY_CHARS``(default 20000)   truncation cap per message

Tracing must never break an LLM call, so every failure path is swallowed
and logged at WARNING level only.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger


logger = get_logger(__name__)

_ENV_ENABLED = "LLM_TRACE_ENABLED"
_ENV_DIR = "LLM_TRACE_DIR"
_ENV_MAX_BODY_CHARS = "LLM_TRACE_MAX_BODY_CHARS"

_DEFAULT_MAX_BODY_CHARS = 20000
_MIN_MAX_BODY_CHARS = 500

# Roleplay fires characters concurrently (asyncio.gather + run_in_executor),
# so appends must be serialized or JSONL lines interleave and corrupt.
_lock = threading.Lock()

# Lazy cache so the toggle can be flipped via env between restarts.
_enabled: Optional[bool] = None


def _now() -> str:
    """Current local time with millisecond precision."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        raw = os.getenv(_ENV_ENABLED, "1")
        _enabled = raw.strip().lower() in ("1", "true", "yes", "on")
    return _enabled


def trace_dir() -> Path:
    """Return the resolved trace output directory (env overridable)."""
    raw = os.getenv(_ENV_DIR, "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "logs" / "llm"


def _max_body_chars() -> int:
    raw = os.getenv(_ENV_MAX_BODY_CHARS, "").strip()
    if not raw:
        return _DEFAULT_MAX_BODY_CHARS
    try:
        return max(_MIN_MAX_BODY_CHARS, int(raw))
    except ValueError:
        return _DEFAULT_MAX_BODY_CHARS


def _truncate(value: Any, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[截断 {len(text) - limit} 字符]"


def _clean_messages(messages: List[Dict[str, Any]], limit: int) -> List[Dict[str, str]]:
    cleaned: List[Dict[str, str]] = []
    for entry in messages:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role", "user")
        content = entry.get("content")
        if content is None:
            content = entry.get("message", "")
        cleaned.append({"role": str(role), "content": _truncate(content, limit)})
    return cleaned


def _json_default(value: Any) -> Any:
    """Coerce pydantic / arbitrary objects into JSON-serializable values."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)


def _append(record: Dict[str, Any]) -> None:
    try:
        directory = trace_dir()
        directory.mkdir(parents=True, exist_ok=True)
        today = time.strftime("%Y-%m-%d")
        path = directory / f"{today}.jsonl"
        line = json.dumps(record, ensure_ascii=False, default=_json_default)
        with _lock:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - tracing must never break a call
        logger.warning("写入 LLM 追踪日志失败: %s", exc)


def trace_llm_chat(
    *,
    model: str,
    kind: str,
    messages: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    response: Any = None,
    reasoning: Any = None,
    usage: Any = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Record one LLM chat call as a JSONL line.

    Args:
        model: Model name the request was sent to.
        kind: Caller category, e.g. ``"roleplay"`` or ``"story_generation"``.
        messages: The full request body (system + history + user).
        context: Optional caller-supplied game context (phase, character...).
        response: Model output text.
        reasoning: Thinking/chain-of-thought text when the provider returned it.
        usage: Token usage (OpenAI CompletionUsage or any JSON-able value).
        duration_ms: Wall-clock latency of the call.
        error: Failure message when the call raised.
    """
    if not _is_enabled():
        return
    limit = _max_body_chars()
    record = {
        "ts": _now(),
        "kind": kind,
        "model": model,
        "messages": _clean_messages(messages, limit),
        "context": context or {},
        "response": response if response is not None else "",
        "reasoning": _truncate(reasoning or "", limit),
        "usage": usage,
        "duration_ms": duration_ms,
        "error": error,
    }
    _append(record)
