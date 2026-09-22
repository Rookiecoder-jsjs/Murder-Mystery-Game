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
from app.domain.models import StoryArchive
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


class TestRevealFlagsStayOutOfTheArchive:
    """哪些线索已公开属于单局运行时状态（由会话快照的
    ``revealed_clue_ids`` 承载），剧本存档只放静态数据。

    曾经的做法是把运行时的 ``reveal_to_all`` 直接写回存档：肖像后台线程
    保存存档时，同局游戏已经在搜证、正在把场景线索翻成公开，于是整局
    进度被写进剧本 JSON，下次载入时开局自带一堆已公开线索。
    """

    def test_to_dict_pins_reveal_to_false(self, sample_archive):
        sample_archive.clues[0].reveal_to_all = True
        data = sample_archive.to_dict()
        assert all(c["reveal_to_all"] is False for c in data["clues"])

    def test_from_dict_discards_stored_reveal_flags(self, sample_archive):
        data = sample_archive.to_dict()
        data["clues"][0]["reveal_to_all"] = True
        restored = StoryArchive.from_dict(data)
        assert all(c.reveal_to_all is False for c in restored.clues)
        assert [c.id for c in restored.clues] == [
            c.id for c in sample_archive.clues
        ]

    def test_parse_ignores_llm_reveal_to_all(self):
        """模型常把证词类线索标成公开；prompt 里的示例说的是 false，
        但没有校验，所以解析层必须自己兜住。"""
        case_data = dict(CASE_DATA)
        case_data["clues"] = [{
            "id": "clue_1",
            "content": "线索内容",
            "type": "testimony",
            "holder_id": "char_1",
            "reveal_to_all": True,
            "required_clue_id": None,
        }]
        archive = ss.parse_case_to_archive(case_data, "测试主题")
        assert archive.clues[0].reveal_to_all is False


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
