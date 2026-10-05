"""Versioned original content. Built-ins are read-only; sessions freeze copies."""
from __future__ import annotations

import json
from pathlib import Path
import re
import uuid

from app.domain.game_manager import GameManager
from app.domain.models import StoryArchive

CONTENT_DIR = Path(__file__).resolve().parents[1] / 'content' / 'stories'
ARTWORK_DIR = Path(__file__).resolve().parents[1] / 'content' / 'images'
MAX_PACKAGE_BYTES = 2 * 1024 * 1024


def _apply_builtin_artwork(archive: StoryArchive, artwork: dict) -> None:
    """Only locally published packages may point to bundled illustrations."""
    def url(name: str) -> str:
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.webp', name):
            raise ValueError('内置配图文件名无效')
        return f'/assets/story-library/{archive.id}/{name}'

    if not isinstance(artwork, dict):
        raise ValueError('内置配图清单无效')
    if artwork.get('cover'):
        archive.catalog['cover_url'] = url(artwork['cover'])
    retained = artwork.get('retained_files', [])
    if not isinstance(retained, list):
        raise ValueError('内置配图保留清单无效')
    for name in retained:
        url(name)
    portraits = artwork.get('portraits', {})
    if not isinstance(portraits, dict) or set(portraits) - {c.id for c in archive.characters}:
        raise ValueError('内置配图角色不存在')
    for character in archive.characters:
        if character.id in portraits:
            character.portrait_url = url(portraits[character.id])


def validate_character_count(count: int | None) -> None:
    if count is not None and (type(count) is not int or not 3 <= count <= 8):
        raise ValueError('角色数量必须为 3—8，自动模式不填写人数')


def _metadata(raw: dict, origin: str) -> dict:
    if not isinstance(raw, dict) or type(raw.get('version')) is not int or raw['version'] < 1:
        raise ValueError('剧本包必须提供正整数内容版本')
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        raise ValueError('不支持此剧本格式版本')
    result = {'version': raw['version'], 'schema_version': 1, 'origin': origin}
    for key, limit in [('summary', 300), ('author', 100), ('license', 300), ('difficulty', 20)]:
        value = raw.get(key, '')
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f'剧本包的 {key} 缺失或过长')
        result[key] = value
    minutes = raw.get('estimated_minutes')
    if type(minutes) is not int or not 5 <= minutes <= 600:
        raise ValueError('预计时长必须为 5—600 分钟')
    result['estimated_minutes'] = minutes
    return result


def parse_package(package: dict, origin: str = 'imported') -> StoryArchive:
    """Import data only: no code execution, online review, or portrait requests."""
    if not isinstance(package, dict) or type(package.get('format_version')) is not int or package['format_version'] != 1:
        raise ValueError('不支持此剧本包，请使用 format_version=1 的 JSON 文件')
    if len(json.dumps(package, ensure_ascii=False).encode()) > MAX_PACKAGE_BYTES:
        raise ValueError('剧本包不能超过 2 MB')
    try:
        raw = package['archive']
        canonical_id = str(uuid.UUID(raw['id']))
        if canonical_id != raw['id']:
            raise ValueError('剧本 ID 必须为标准 UUID')
        metadata = _metadata(package['metadata'], origin)
        # Reject invalid holders before legacy normalization can conceal a typo.
        ids = {c['id'] for c in raw['characters']}
        if any(c['holder_id'] not in ids | {'scene'} for c in raw['clues']):
            raise ValueError('线索持有者不存在')
        archive = StoryArchive.from_dict(raw)
        if not 3 <= len(archive.characters) <= 8 or not 3 <= len(archive.clues) <= 60:
            raise ValueError('剧本包须包含 3—8 个角色和 3—60 条线索')
        if not archive.title.strip() or not archive.story_content.strip():
            raise ValueError('剧本标题和真相不能为空')
        archive.validate(require_script=True, require_solution=True)
        GameManager.validate_quick_evidence_routes(archive)
        archive.catalog = metadata
        # Arbitrary packages cannot assert that they passed our editorial review.
        archive.production = {'status': 'ready', 'origin': origin,
                              'validation': 'local-structure-and-routes-v1'}
        for character in archive.characters:
            character.portrait_url = ''
        return archive
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('剧本包内容结构不完整') from exc


def builtin_stories() -> list[StoryArchive]:
    """Read only manifest-listed assets, never scan personal story folders."""
    manifest = CONTENT_DIR / 'manifest.json'
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('format_version') != 1:
        raise ValueError('内置剧本目录版本不支持')
    result = []
    for name in data['packages']:
        if not isinstance(name, str) or Path(name).name != name or not name.endswith('.json'):
            raise ValueError('内置剧本文件名无效')
        package = json.loads((CONTENT_DIR / name).read_text(encoding='utf-8'))
        archive = parse_package(package, 'builtin')
        _apply_builtin_artwork(archive, package.get('artwork', {}))
        result.append(archive)
    if len({a.id for a in result}) != len(result):
        raise ValueError('内置剧本 ID 重复')
    return result


def story_info(archive: StoryArchive) -> dict:
    metadata = archive.catalog if isinstance(archive.catalog, dict) else {}
    return {'id': archive.id, 'title': archive.title, 'topic': archive.topic,
            'created_at': archive.created_at, 'num_characters': len(archive.characters),
            'origin': metadata.get('origin', 'generated' if archive.production.get('origin') == 'generated' else 'legacy'),
            'version': metadata.get('version', 1),
            'delivery': metadata.get('delivery'),
            'cover_url': metadata.get('cover_url', ''),
            **{key: metadata.get(key, '') for key in ('summary', 'difficulty', 'author', 'license')},
            'estimated_minutes': metadata.get('estimated_minutes')}
