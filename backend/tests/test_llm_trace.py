"""Tests for the LLM call trace logger (JSONL records)."""

from __future__ import annotations

import json

from app.core import llm_trace
from app.core.llm_trace import trace_llm_chat


class _Usage:
    """Minimal stand-in for OpenAI CompletionUsage (pydantic model_dump)."""

    def model_dump(self) -> dict:
        return {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def _read_records(path):
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line]


def test_writes_jsonl_record(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_trace, "_is_enabled", lambda: True)
    monkeypatch.setattr(llm_trace, "trace_dir", lambda: tmp_path)

    messages = [
        {"role": "system", "content": "你是侦探。"},
        {"role": "user", "content": "谁是凶手？"},
    ]
    trace_llm_chat(
        model="deepseek-v4-flash",
        kind="roleplay",
        messages=messages,
        context={"phase": "discussion", "character_id": "char_1"},
        response="我觉得是 Alice。",
        reasoning="Alice 的线索指向她。",
        usage=_Usage(),
        duration_ms=1234,
    )

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    records = _read_records(files[0])
    assert len(records) == 1
    record = records[0]
    assert record["kind"] == "roleplay"
    assert record["model"] == "deepseek-v4-flash"
    assert record["messages"] == messages
    assert record["context"] == {"phase": "discussion", "character_id": "char_1"}
    assert record["response"] == "我觉得是 Alice。"
    assert record["reasoning"] == "Alice 的线索指向她。"
    assert record["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert record["duration_ms"] == 1234
    assert record["error"] is None
    assert record["ts"]


def test_disabled_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_trace, "_is_enabled", lambda: False)
    monkeypatch.setattr(llm_trace, "trace_dir", lambda: tmp_path)

    trace_llm_chat(model="m", kind="k", messages=[{"role": "user", "content": "hi"}])

    assert not list(tmp_path.glob("*.jsonl"))


def test_truncates_long_bodies(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_trace, "_is_enabled", lambda: True)
    monkeypatch.setattr(llm_trace, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(llm_trace, "_max_body_chars", lambda: 50)

    long_text = "长" * 500
    trace_llm_chat(
        model="m",
        kind="k",
        messages=[{"role": "user", "content": long_text}],
        reasoning=long_text,
    )

    files = list(tmp_path.glob("*.jsonl"))
    record = _read_records(files[0])[0]
    content = record["messages"][0]["content"]
    assert content.startswith("长" * 50)
    assert "[截断" in content
    assert len(content) < 200
    assert "[截断" in record["reasoning"]


def test_env_toggle_and_dir(monkeypatch, tmp_path):
    # Disabled via env → no file.
    monkeypatch.setattr(llm_trace, "_enabled", None)
    monkeypatch.setenv("LLM_TRACE_ENABLED", "0")
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    trace_llm_chat(model="m", kind="k", messages=[{"role": "user", "content": "hi"}])
    assert not list(tmp_path.glob("*.jsonl"))

    # Re-enabled via env → record lands in the env-chosen directory.
    monkeypatch.setattr(llm_trace, "_enabled", None)
    monkeypatch.setenv("LLM_TRACE_ENABLED", "1")
    trace_llm_chat(model="m", kind="k", messages=[{"role": "user", "content": "hi"}])
    assert len(list(tmp_path.glob("*.jsonl"))) == 1


def test_write_failure_is_swallowed(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_trace, "_is_enabled", lambda: True)
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setattr(llm_trace, "trace_dir", lambda: blocker)

    # Trace must never raise, even when the target directory is unwritable.
    trace_llm_chat(model="m", kind="k", messages=[{"role": "user", "content": "hi"}])
