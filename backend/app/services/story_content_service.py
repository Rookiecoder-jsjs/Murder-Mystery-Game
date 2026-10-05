"""Trusted installed content, isolated from personal stories and frozen sessions.

Android verifies signatures and files before calling the fixed installation
entry points. No HTTP or arbitrary package can assert trusted provenance here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid

from app.domain.models import StoryArchive
from app.services import story_catalog
from app.core.content_protocol import strict_json, artwork_files, content_fingerprint

ENGINE_VERSION = 1
CONTENT_LOCK = threading.RLock()
_directory: Path | None = None
_cache_key: tuple | None = None
_cache: list[dict] = []
_HASH = re.compile(r'[a-f0-9]{64}')


def configure(directory: str | Path | None) -> None:
    """Select the app-owned installation store; never scan arbitrary folders."""
    global _directory, _cache_key, _cache
    _directory = Path(directory).resolve() if directory else None
    _cache_key, _cache = None, []


def builtin_fingerprints() -> dict[str, str]:
    path = story_catalog.CONTENT_DIR / 'manifest.json'
    if not path.exists():
        return {}
    manifest = strict_json(path.read_bytes())
    if 'content_fingerprints' in manifest:
        return manifest['content_fingerprints']
    result = {}
    for name in manifest['packages']:
        if Path(name).name != name:
            raise ValueError('内置文件名无效')
        raw = (path.parent / name).read_bytes()
        package = strict_json(raw)
        images = {image: (story_catalog.ARTWORK_DIR / package['archive']['id'] / image).read_bytes()
                  for image in artwork_files(package)}
        result[package['archive']['id']] = content_fingerprint(raw, images)
    return result


def read_registry() -> dict:
    if _directory is None or not (_directory / 'registry.json').exists():
        return {'registry_format': 1, 'library_revision': 0, 'stories': {}}
    path = _directory / 'registry.json'
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('本地内容索引超过限制')
    data = strict_json(path.read_bytes())
    if data.get('registry_format') != 1 or type(data.get('library_revision')) is not int or not isinstance(data.get('stories'), dict):
        raise ValueError('本地内容索引损坏，请保留存档并重试')
    return data


def _pack_path(story_id: str, version: int, digest: str) -> Path:
    if _directory is None or str(uuid.UUID(story_id)) != story_id or type(version) is not int or version < 1 or not _HASH.fullmatch(digest):
        raise ValueError('内容版本或路径无效')
    return _directory / 'packs' / story_id / f'v{version}-{digest}'


def _read_package(directory: Path, digest: str) -> tuple[StoryArchive, str]:
    path = directory / 'package.json'
    if path.stat().st_size > story_catalog.MAX_PACKAGE_BYTES:
        raise ValueError('剧本包不能超过 2 MB')
    raw = path.read_bytes()
    package = strict_json(raw)
    archive = story_catalog.parse_package(package, 'builtin')
    names = artwork_files(package)
    # Reuse existing role mapping validation, then derive immutable URLs.
    story_catalog._apply_builtin_artwork(archive, package.get('artwork', {}))
    images = {}
    for name in names:
        image = directory / 'images' / name
        if image.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('配图文件超过限制')
        images[name] = image.read_bytes()
    image_directory = directory / 'images'
    if image_directory.exists() and {p.name for p in image_directory.iterdir()} != names:
        raise ValueError('配图文件与 artwork 清单不同')
    fingerprint = content_fingerprint(raw, images)
    version = archive.catalog['version']
    prefix = f'/assets/story-library/packs/{archive.id}/{version}/{digest}/'
    art = package.get('artwork', {})
    archive.catalog['cover_url'] = prefix + art['cover'] if art.get('cover') else ''
    for char in archive.characters:
        image = art.get('portraits', {}).get(char.id)
        char.portrait_url = prefix + image if image else ''
    archive.catalog.update(delivery='downloaded', content_ref={
        'story_id': archive.id, 'version': version, 'bundle_sha256': digest, 'delivery': 'downloaded'})
    return archive, fingerprint


def validate_package(directory: str, digest: str) -> dict:
    """Fixed native entry point after signature/extraction checks; no mutation."""
    if _directory is None or not _HASH.fullmatch(digest):
        raise ValueError('内容库尚未初始化')
    candidate = Path(directory).resolve()
    if not candidate.is_relative_to(_directory / 'staging') and not candidate.is_relative_to(_directory / 'packs'):
        raise ValueError('安装目录无效')
    archive, fingerprint = _read_package(candidate, digest)
    return {**story_catalog.story_info(archive), 'fingerprint': fingerprint}


def _write_registry(registry: dict) -> None:
    assert _directory is not None
    _directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='registry-', suffix='.tmp', dir=_directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(registry, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, _directory / 'registry.json')
        descriptor = os.open(_directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def activate(story_id: str, version: int, digest: str, personal_directory: str) -> dict:
    """Commit one native-verified pack under the shared story namespace lock."""
    path = _pack_path(story_id, version, digest)
    archive, fingerprint = _read_package(path, digest)
    if archive.id != story_id or archive.catalog['version'] != version:
        raise ValueError('内容 ID 或版本不一致')
    marker = strict_json((path / 'complete.json').read_bytes())
    if marker.get('story_id') != story_id or marker.get('version') != version or marker.get('sha256') != digest or marker.get('fingerprint') != fingerprint or marker.get('min_engine_version', 1) > ENGINE_VERSION:
        raise ValueError('安装尚未完成或引擎不兼容')
    with CONTENT_LOCK:
        registry = read_registry()
        if (Path(personal_directory) / f'{story_id}.json').exists():
            raise ValueError('ID_CONFLICT: 个人剧本使用了相同 ID，已保留个人内容')
        baseline = next((a for a in story_catalog.builtin_stories() if a.id == story_id), None)
        record = registry['stories'].get(story_id, {'highest_version': 0, 'versions': []})
        highest = max(record['highest_version'], baseline.catalog['version'] if baseline else 0)
        if version < highest:
            raise ValueError('VERSION_CONFLICT: 不能安装旧版本')
        if baseline and version == baseline.catalog['version'] and builtin_fingerprints().get(story_id) != fingerprint:
            raise ValueError('VERSION_CONFLICT: 同版本基础内容不同')
        old = next((row for row in record['versions'] if row['version'] == version), None)
        if old and old['sha256'] != digest:
            raise ValueError('VERSION_CONFLICT: 同版本内容不同')
        if old and old.get('active'):
            return story_catalog.story_info(archive)
        row = {'version': version, 'sha256': digest, 'fingerprint': fingerprint,
               'min_engine_version': marker.get('min_engine_version', 1), 'active': True}
        if old:
            old.update(row)
        else:
            record['versions'].append(row)
        record['highest_version'] = max(highest, version)
        registry['stories'][story_id] = record
        registry['library_revision'] += 1
        _write_registry(registry)
    return story_catalog.story_info(archive)


def deactivate(story_id: str) -> None:
    with CONTENT_LOCK:
        registry = read_registry()
        if story_id not in registry['stories']:
            raise ValueError('此剧本没有下载版本')
        for row in registry['stories'][story_id]['versions']:
            row['active'] = False
        registry['library_revision'] += 1
        _write_registry(registry)


def owns_id(story_id: str) -> bool:
    return story_id in read_registry()['stories']


def is_installed(story_id: str, version: int, digest: str) -> bool:
    """Acknowledge only a complete, active pack, including crash recovery."""
    record = read_registry()['stories'].get(story_id, {})
    row = next((r for r in record.get('versions', [])
                if r['version'] == version and r['sha256'] == digest and r.get('active')), None)
    if row is None or row.get('min_engine_version', 1) > ENGINE_VERSION:
        return False
    try:
        directory = _pack_path(story_id, version, digest)
        marker = strict_json((directory / 'complete.json').read_bytes())
        archive, fingerprint = _read_package(directory, digest)
        return (archive.id == story_id and archive.catalog['version'] == version
                and marker.get('story_id') == story_id and marker.get('version') == version
                and marker.get('sha256') == digest
                and marker.get('fingerprint') == fingerprint == row['fingerprint'])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def installed_stories() -> list[StoryArchive]:
    """Read a consistent registry generation; return independent archive copies."""
    global _cache_key, _cache
    if _directory is None:
        return []
    registry = read_registry()
    key = (str(_directory), registry['library_revision'])
    with CONTENT_LOCK:
        if key != _cache_key:
            archives = []
            for story_id, record in registry['stories'].items():
                for row in sorted(record['versions'], key=lambda r: r['version'], reverse=True):
                    if not row.get('active') or row.get('min_engine_version', 1) > ENGINE_VERSION:
                        continue
                    try:
                        directory = _pack_path(story_id, row['version'], row['sha256'])
                        marker = strict_json((directory / 'complete.json').read_bytes())
                        if marker.get('story_id') != story_id or marker.get('version') != row['version'] or marker.get('sha256') != row['sha256'] or marker.get('fingerprint') != row['fingerprint']:
                            continue
                        archive, fingerprint = _read_package(directory, row['sha256'])
                        if archive.id == story_id and archive.catalog['version'] == row['version'] and fingerprint == row['fingerprint']:
                            archives.append(archive.to_dict())
                            break
                    except (OSError, ValueError, KeyError, TypeError):
                        continue
            _cache_key, _cache = key, archives
        return [StoryArchive.from_dict(data) for data in _cache]


def official_stories() -> list[StoryArchive]:
    result = {a.id: a for a in story_catalog.builtin_stories()}
    try:
        downloaded = installed_stories()
    except (OSError, ValueError):
        downloaded = []  # A damaged downloaded index must not hide APK cases.
    for archive in result.values():
        archive.catalog.update(delivery='bundled', content_ref={'story_id': archive.id,
            'version': archive.catalog['version'], 'bundle_sha256': None, 'delivery': 'bundled'})
    for archive in downloaded:
        if archive.id not in result or archive.catalog['version'] >= result[archive.id].catalog['version']:
            result[archive.id] = archive
    return list(result.values())
