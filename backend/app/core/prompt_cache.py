"""Prompt-prefix diagnostics and provider-reported cache usage.

No model output or private context is cached here. Fingerprints are local
diagnostics, not provider cache keys or proof of a cache hit.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def prefix_fingerprint(*, model: str, system: str, context_prefix: str,
                       tools: list | None, tool_choice: dict | None, thinking: bool) -> str:
    """Identify the fixed request prefix, including model/tool configuration."""
    value = {"model": model, "system": system, "context_prefix": context_prefix,
             "tools": tools, "tool_choice": tool_choice, "thinking": thinking}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def cache_usage(usage: Any) -> dict:
    """Normalize reported tokens; absent/invalid metrics remain unknown."""
    if hasattr(usage, "model_dump"):
        try:
            usage = usage.model_dump()
        except Exception:
            usage = None  # Diagnostics must never prevent delivery of a reply.
    if not isinstance(usage, dict):
        usage = {}

    def count(value):
        return value if type(value) is int and value >= 0 else None

    prompt = count(usage.get("prompt_tokens"))
    hit = count(usage.get("prompt_cache_hit_tokens"))
    miss = count(usage.get("prompt_cache_miss_tokens"))
    details = usage.get("prompt_tokens_details")
    if hit is None and isinstance(details, dict):
        hit = count(details.get("cached_tokens"))
    if prompt is None and hit is not None and miss is not None:
        prompt = hit + miss
    if prompt is not None and hit is not None:
        if hit > prompt or (miss is not None and hit + miss != prompt):
            hit = miss = None
        else:
            miss = prompt - hit
    return {"prompt_tokens": prompt, "hit_tokens": hit, "miss_tokens": miss,
            "hit_rate": hit / prompt if prompt and hit is not None else None}


def summarize_cache(records: Iterable[dict]) -> list[dict]:
    """Token-weighted per-role/stage statistics, separating missing reports."""
    groups = {}
    for record in records:
        if record.get("kind") != "roleplay":
            continue
        context = record.get("context") or {}
        stage = context.get("stage") or ("voting" if context.get("via") == "function_call" else "generation")
        key = (record.get("model", ""), context.get("game_id", ""),
               context.get("character_id", ""), stage)
        group = groups.setdefault(key, dict(zip(("model", "game_id", "character_id", "stage"), key)) | {
            "calls": 0, "reported_calls": 0, "unknown_calls": 0, "errors": 0,
            "prompt_tokens": 0, "hit_tokens": 0, "miss_tokens": 0,
        })
        group["calls"] += 1
        group["errors"] += bool(record.get("error"))
        usage = cache_usage(record.get("usage"))
        if usage["prompt_tokens"] is None or usage["hit_tokens"] is None:
            group["unknown_calls"] += 1
            continue
        group["reported_calls"] += 1
        for field in ("prompt_tokens", "hit_tokens", "miss_tokens"):
            group[field] += usage[field]
    for group in groups.values():
        group["hit_rate"] = group["hit_tokens"] / group["prompt_tokens"] if group["prompt_tokens"] else None
    return list(groups.values())


def main() -> None:
    """Read local traces without printing prompts, replies or secret material."""
    parser = argparse.ArgumentParser(description="按角色/阶段统计供应商实际返回的缓存用量")
    parser.add_argument("paths", nargs="*", type=Path, help="JSONL 日志路径，默认读取 logs/llm 下全部日志")
    parser.add_argument("--game-id", help="只统计指定游戏")
    args = parser.parse_args()
    if not args.paths:
        from app.core.llm_trace import trace_dir
        args.paths = sorted(trace_dir().glob("*.jsonl"))

    def records():
        for path in args.paths:
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue  # A writer may still be appending the last line.
                    if isinstance(record, dict) and (not args.game_id or
                            (record.get("context") or {}).get("game_id") == args.game_id):
                        yield record

    print(json.dumps(summarize_cache(records()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
