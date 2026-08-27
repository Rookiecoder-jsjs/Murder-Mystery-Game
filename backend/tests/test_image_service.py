"""Tests for character portrait generation without calling DashScope."""

from __future__ import annotations

import json

from app.core.config import QwenImageConfig
from app.services import image_service
from app.services.image_service import PortraitService, build_portrait_prompt


class _Headers:
    def __init__(self, content_type: str = "application/json"):
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type


class _Response:
    def __init__(self, data: bytes, content_type: str = "application/json"):
        self._data = data
        self.headers = _Headers(content_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self._data


def _config() -> QwenImageConfig:
    return QwenImageConfig(
        api_key="test-key",
        base_url="https://example.test/api/v1",
        timeout_seconds=1,
        poll_interval_seconds=0.1,
        max_workers=1,
        request_timeout_seconds=1,
    )


def test_prompt_uses_public_profile_without_secrets(sample_archive):
    character = sample_archive.characters[0]
    prompt = build_portrait_prompt(character, sample_archive.case)

    assert character.name in prompt
    assert character.public_identity in prompt
    assert character.appearance in prompt
    assert character.secret not in prompt
    assert character.motive not in prompt


def test_generates_downloads_and_persists_portrait(monkeypatch, tmp_path, sample_archive):
    replies = iter([
        _Response(json.dumps({"output": {"task_id": "task-1"}}).encode()),
        _Response(json.dumps({
            "output": {
                "task_status": "SUCCEEDED",
                "choices": [{"message": {"content": [{
                    "image": "https://images.example.test/portrait.png"
                }]}}],
            }
        }).encode()),
        _Response(b"fake-png", "image/png"),
    ])
    monkeypatch.setattr(image_service, "PORTRAITS_DIR", tmp_path / "portraits")
    monkeypatch.setattr(image_service, "urlopen", lambda *_args, **_kwargs: next(replies))

    service = PortraitService(_config())
    result = service.generate_portrait(
        sample_archive.id,
        sample_archive.characters[0],
        sample_archive.case,
    )

    assert result == "/assets/portraits/story_test/char_1.png"
    assert (tmp_path / "portraits" / "story_test" / "char_1.png").read_bytes() == b"fake-png"


def test_archive_generation_updates_each_character(monkeypatch, sample_archive):
    service = PortraitService(_config())
    monkeypatch.setattr(
        service,
        "generate_portrait",
        lambda story_id, character, case: f"/assets/portraits/{story_id}/{character.id}.png",
    )

    assert service.generate_for_archive(sample_archive) == len(sample_archive.characters)
    assert all(character.portrait_url for character in sample_archive.characters)
