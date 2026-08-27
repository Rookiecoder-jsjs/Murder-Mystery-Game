"""Qwen Image portrait generation and local persistence.

The DashScope result URL is short-lived, so this module downloads each
portrait immediately and stores it beside the story archive's local assets.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import QwenImageConfig, get_config
from app.core.logging import get_logger
from app.domain.models import CaseData, ScriptCharacter, StoryArchive


logger = get_logger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
PORTRAITS_DIR = _BACKEND_DIR / "assets" / "portraits"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_TERMINAL_FAILURES = {"FAILED", "CANCELED", "UNKNOWN"}
_CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/png": ".png",
}


class ImageGenerationError(RuntimeError):
    """Raised when the image provider cannot produce a usable portrait."""


def _safe_id(value: str) -> str:
    """Validate IDs before using them as filesystem path components."""
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"非法的资源标识: {value!r}")
    return value


def ensure_portraits_dir() -> None:
    """Create the local portrait root when it does not yet exist."""
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)


def portrait_url(story_id: str, character_id: str, suffix: str = ".png") -> str:
    """Return the stable API-relative URL for one persisted portrait."""
    return f"/assets/portraits/{_safe_id(story_id)}/{_safe_id(character_id)}{suffix}"


def build_portrait_prompt(character: ScriptCharacter, case: CaseData) -> str:
    """Build a public, era-appropriate character portrait prompt.

    Secrets, alibis, motives, and killer status are deliberately excluded so
    a portrait cannot disclose information that players should not see.
    """
    setting = "，".join(part for part in (case.time, case.location) if part) or "1930年代中国"
    appearance = character.appearance.strip() or "五官清晰、神态与身份相称"
    identity = character.public_identity.strip() or "案件相关人物"
    return (
        "为1930年代中国本格推理剧本杀创作一张单人角色档案肖像。"
        f"角色名：{character.name}；公开身份：{identity}；外貌：{appearance}；"
        f"故事时空：{setting}。"
        "画面为竖幅 2:3、半身至胸像、正面或微侧脸的人像摄影，"
        "人物是唯一主体，神情克制而富有故事感，服装、发型、妆容与时代和身份严格一致。"
        "背景是低细节的年代室内或街景，柔和电影光影、胶片颗粒、档案照片质感，"
        "面部清晰、双手不入镜。不要姓名、文字、签名、边框、水印、徽标、现代物品、"
        "多人物、畸形五官或额外肢体。"
    )


class PortraitService:
    """Generate Qwen Image portraits and persist them under ``PORTRAITS_DIR``."""

    def __init__(self, config: QwenImageConfig | None = None):
        self.config = config or get_config().qwen_image

    @property
    def is_configured(self) -> bool:
        return bool(self.config.api_key.strip())

    def generate_for_archive(self, archive: StoryArchive) -> int:
        """Generate portraits for every character without failing the story.

        The upstream API is asynchronous. A small thread pool keeps the story
        creation latency reasonable without burst-submitting the whole cast.
        """
        if not self.is_configured:
            logger.info("未配置 DASHSCOPE_API_KEY，跳过角色肖像生成")
            return 0

        characters = [c for c in archive.characters if not c.portrait_url]
        if not characters:
            return 0

        saved = 0
        worker_count = min(self.config.max_workers, len(characters))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self.generate_portrait, archive.id, char, archive.case): char
                for char in characters
            }
            for future in as_completed(futures):
                character = futures[future]
                try:
                    character.portrait_url = future.result()
                    saved += 1
                    logger.info("角色肖像已生成: %s", character.name)
                except (ImageGenerationError, OSError, ValueError) as exc:
                    logger.warning("角色肖像生成失败（%s）: %s", character.name, exc)

        return saved

    def generate_portrait(
        self,
        story_id: str,
        character: ScriptCharacter,
        case: CaseData,
    ) -> str:
        """Generate, download, and return the local URL for one character."""
        if not self.is_configured:
            raise ImageGenerationError("未配置 DASHSCOPE_API_KEY")

        prompt = build_portrait_prompt(character, case)
        task = self._request_json(
            "/services/aigc/image-generation/generation",
            method="POST",
            payload={
                "model": self.config.model_name,
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": [{"text": prompt}],
                    }],
                },
                "parameters": {
                    "size": self.config.size,
                    "n": 1,
                    "prompt_extend": False,
                    "watermark": False,
                },
            },
            headers={"X-DashScope-Async": "enable"},
        )
        task_id = str(task.get("output", {}).get("task_id", ""))
        if not task_id:
            raise ImageGenerationError("图像服务未返回任务 ID")

        completed = self._wait_for_task(task_id)
        image_url = self._extract_image_url(completed)
        return self._download_image(story_id, character.id, image_url)

    def _wait_for_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.timeout_seconds
        while True:
            result = self._request_json(f"/tasks/{task_id}")
            output = result.get("output", {})
            status = str(output.get("task_status", "")).upper()
            if status == "SUCCEEDED":
                return result
            if status in _TERMINAL_FAILURES:
                message = output.get("message") or result.get("message") or status
                raise ImageGenerationError(f"图像任务失败: {message}")
            if time.monotonic() >= deadline:
                raise ImageGenerationError("图像任务超时")
            time.sleep(self.config.poll_interval_seconds)

    def _request_json(
        self,
        path: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        request_headers = {"Authorization": f"Bearer {self.config.api_key}"}
        if headers:
            request_headers.update(headers)
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ImageGenerationError(f"图像服务请求失败（HTTP {exc.code}）: {detail}") from exc
        except URLError as exc:
            raise ImageGenerationError(f"无法连接图像服务: {exc.reason}") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ImageGenerationError("图像服务返回了无效 JSON") from exc
        if not isinstance(data, dict):
            raise ImageGenerationError("图像服务返回格式不正确")
        return data

    @staticmethod
    def _extract_image_url(result: dict[str, Any]) -> str:
        choices = result.get("output", {}).get("choices", [])
        for choice in choices if isinstance(choices, list) else []:
            content = choice.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                image_url = block.get("image") if isinstance(block, dict) else None
                if isinstance(image_url, str) and image_url:
                    parsed = urlparse(image_url)
                    if parsed.scheme == "https" and parsed.netloc:
                        return image_url
        raise ImageGenerationError("图像任务未返回可下载的图片")

    def _download_image(self, story_id: str, character_id: str, image_url: str) -> str:
        request = Request(image_url, headers={"User-Agent": "MurderMystery/1.0"})
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                content_type = response.headers.get_content_type().lower()
                image = response.read(_MAX_IMAGE_BYTES + 1)
        except (HTTPError, URLError, OSError) as exc:
            raise ImageGenerationError(f"下载生成图片失败: {exc}") from exc
        if len(image) > _MAX_IMAGE_BYTES:
            raise ImageGenerationError("生成图片超过 20MB 上限")
        if not image:
            raise ImageGenerationError("生成图片为空")

        suffix = _CONTENT_TYPE_SUFFIXES.get(content_type, ".png")
        story_dir = PORTRAITS_DIR / _safe_id(story_id)
        story_dir.mkdir(parents=True, exist_ok=True)
        destination = story_dir / f"{_safe_id(character_id)}{suffix}"
        temporary = destination.with_suffix(f"{suffix}.tmp")
        try:
            temporary.write_bytes(image)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        return portrait_url(story_id, character_id, suffix)


def delete_story_portraits(story_id: str) -> None:
    """Remove assets belonging to one deleted story, never the portrait root."""
    root = PORTRAITS_DIR.resolve()
    story_dir = (PORTRAITS_DIR / _safe_id(story_id)).resolve()
    if root not in story_dir.parents:
        raise ValueError("拒绝删除肖像根目录")
    if story_dir.exists():
        shutil.rmtree(story_dir)
