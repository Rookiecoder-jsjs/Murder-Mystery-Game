# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Tests for StoryService.create_story portrait handling.

Portrait generation must run in the background: the archive is saved and
returned immediately so a new game can start, then a daemon thread writes
portrait URLs back. No network access — module functions are patched.
"""

from __future__ import annotations

import threading
import time

from app.core.config import QwenImageConfig
from app.services import story_service as ss
from app.services.image_service import PortraitService

CASE_DATA = {
    "title": "测试案",
    "background": "案件背景",
    "location": "地点",
    "time": "时间",
    "victim": {"name": "受害者"},
    "true_killer_id": "char_1",
    "characters": [
        {"id": "char_1", "name": "张三"},
        {"id": "char_2", "name": "李四"},
    ],
    "clues": [],
    "truth": "真相叙述",
}


def _patch_llm(monkeypatch) -> None:
    """Short-circuit story generation so no LLM/network is involved."""
    monkeypatch.setattr(ss, "create_deepseek_client", lambda: None)
    monkeypatch.setattr(
        ss, "generate_story",
        lambda topic, client, show_reasoning=False: dict(CASE_DATA),
    )


def _service_with_key(api_key: str) -> ss.StoryService:
    svc = ss.StoryService()
    svc.portrait_service = PortraitService(config=QwenImageConfig(api_key=api_key))
    return svc


class TestCreateStoryPortraits:
    def test_returns_archive_immediately_when_portraits_skipped(self, monkeypatch):
        """No DashScope key -> one save (no portrait urls), return right away."""
        _patch_llm(monkeypatch)
        saves: list = []
        monkeypatch.setattr(ss, "save_story", lambda archive: saves.append(archive))
        generated: list = []
        monkeypatch.setattr(
            PortraitService, "generate_for_archive",
            lambda self_, archive: generated.append(archive) or 0,
        )
        svc = _service_with_key("")

        archive = svc.create_story("深夜当铺命案")

        assert archive is not None
        assert archive.title == "测试案"
        assert len(saves) == 1  # persisted before returning
        assert generated == []  # portraits never attempted when unconfigured

    def test_portraits_run_in_background_and_persist_urls(self, monkeypatch):
        """Configured -> initial save returns first; a daemon thread later
        writes portrait URLs and triggers a second save."""
        _patch_llm(monkeypatch)
        saves: list = []
        monkeypatch.setattr(ss, "save_story", lambda archive: saves.append(archive))
        started = threading.Event()
        gate = threading.Event()  # held until we assert the early return

        def fake_generate(self_, archive):
            started.set()
            gate.wait(timeout=5)  # hold the thread so ordering is deterministic
            for char in archive.characters:
                char.portrait_url = f"/assets/portraits/x/{char.id}.png"
            return len(archive.characters)

        monkeypatch.setattr(PortraitService, "generate_for_archive", fake_generate)
        svc = _service_with_key("test-key")

        archive = svc.create_story("深夜当铺命案")

        assert archive is not None
        assert started.wait(timeout=5), "background thread was never started"
        assert len(saves) == 1  # returned before any portrait URL was written
        assert all(not c.portrait_url for c in archive.characters)

        gate.set()  # let the background thread finish
        deadline = time.monotonic() + 5
        while len(saves) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(saves) == 2  # second save persists the updated URLs
        assert all(c.portrait_url for c in saves[1].characters)
