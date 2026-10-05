"""Installation commit, namespace races and frozen content; no model/network."""
import copy
import hashlib
import json
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from app.core.content_protocol import artwork_files, content_fingerprint, strict_json
from app.services import story_catalog as catalog, story_content_service as content, story_service as stories
from app.services.session_service import SessionManager, JsonFileSessionStore
from tests.test_session_service import StubRoleplayClient

SOURCE = Path(__file__).resolve().parents[1] / 'app/content'


@pytest.fixture
def library(tmp_path, monkeypatch):
    base = tmp_path / 'base'
    base.mkdir()
    names = json.loads((SOURCE / 'android-base.json').read_text())['packages']
    for name in names:
        (base / name).write_bytes((SOURCE / 'stories' / name).read_bytes())
    (base / 'manifest.json').write_text(json.dumps({'format_version': 1, 'packages': names}))
    monkeypatch.setattr(catalog, 'CONTENT_DIR', base)
    personal = tmp_path / 'personal'
    personal.mkdir()
    monkeypatch.setattr(stories, 'STORIES_DIR', str(personal))
    content.configure(tmp_path / 'library')
    yield tmp_path / 'library', personal
    content.configure(None)


def package(suffix='3304'):
    return json.loads((SOURCE / 'stories' / ('ad60c7e0-1f56-4fc3-bcaa-705910d0' + suffix + '.json')).read_text())


def pack(root, data, digest=None, raw=None, engine=1):
    raw = raw or (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    digest = digest or hashlib.sha256(raw).hexdigest()
    sid, version = data['archive']['id'], data['metadata']['version']
    directory = root / 'packs' / sid / f'v{version}-{digest}'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'package.json').write_bytes(raw)
    images = {}
    for name in artwork_files(data):
        images[name] = (SOURCE / 'images' / sid / name).read_bytes()
        (directory / 'images').mkdir(exist_ok=True)
        (directory / 'images' / name).write_bytes(images[name])
    marker = {'story_id': sid, 'version': version, 'sha256': digest,
              'fingerprint': content_fingerprint(raw, images), 'min_engine_version': engine}
    (directory / 'complete.json').write_text(json.dumps(marker))
    return sid, version, digest, directory


def commit(root, personal, data, **kwargs):
    sid, version, digest, directory = pack(root, data, **kwargs)
    info = content.activate(sid, version, digest, str(personal))
    return info, directory


def test_install_is_visible_only_after_registry_and_does_not_expose_truth(library):
    root, personal = library
    data = package()
    sid, version, digest, directory = pack(root, data)
    assert len(stories.list_stories()) == 3
    result = content.activate(sid, version, digest, str(personal))
    assert result['delivery'] == 'downloaded'
    assert len(stories.list_stories()) == 4
    assert not any(field in json.dumps(stories.list_stories()) for field in ('self_knowledge', 'true_killer', 'solution', 'story_content'))
    before = content.read_registry()
    assert content.activate(sid, version, digest, str(personal)) == result
    assert content.read_registry() == before
    assert (directory / 'complete.json').is_file()
    assert list(personal.iterdir()) == []


def test_crash_recovery_does_not_acknowledge_missing_or_changed_content(library):
    root, personal = library
    sid, version, digest, directory = pack(root, package())
    assert not content.is_installed(sid, version, digest)
    content.activate(sid, version, digest, str(personal))
    assert content.is_installed(sid, version, digest)
    original = (directory / 'package.json').read_bytes()
    (directory / 'package.json').write_bytes(original + b' ')
    assert not content.is_installed(sid, version, digest)
    (directory / 'package.json').write_bytes(original)
    assert content.is_installed(sid, version, digest)
    (directory / 'complete.json').unlink()
    assert not content.is_installed(sid, version, digest)


def test_upgrade_freezes_old_body_roles_and_immutable_images_across_restart(library):
    root, personal = library
    first = package('3301')
    first['metadata']['version'] += 1
    info, old_dir = commit(root, personal, first)
    service = stories.StoryService()
    manager = SessionManager(StubRoleplayClient(), service, JsonFileSessionStore(str(root / 'sessions')))
    gid, old = manager.create_session(archive=service.get_playable_story(info['id']))
    frozen = copy.deepcopy(old.archive.to_dict())
    second = copy.deepcopy(first)
    second['metadata']['version'] += 1
    second['archive']['title'] = '新版案卷'
    _, new_dir = commit(root, personal, second)
    assert old.archive.to_dict() == frozen
    assert service.get_playable_story(info['id']).title == '新版案卷'
    assert old.archive.catalog['cover_url'] != service.get_playable_story(info['id']).catalog['cover_url']
    restarted = SessionManager(StubRoleplayClient(), service, manager._store)
    assert restarted.load_all_persisted() == 1
    assert restarted.get(gid).archive.to_dict() == frozen
    content.deactivate(info['id'])
    assert service.get_playable_story(info['id']).catalog['delivery'] == 'bundled'
    assert old_dir.is_dir() and new_dir.is_dir()
    assert restarted.get(gid).archive.to_dict() == frozen
    assert content.activate(info['id'], second['metadata']['version'], new_dir.name.split('-', 1)[1], str(personal))['delivery'] == 'downloaded'


def test_versions_and_base_fingerprints_reject_changes_without_commit(library):
    root, personal = library
    first = package()
    commit(root, personal, first)
    baseline = content.read_registry()
    changed = copy.deepcopy(first)
    changed['archive']['title'] = '同版本改稿'
    with pytest.raises(ValueError, match='VERSION_CONFLICT'):
        commit(root, personal, changed)
    assert content.read_registry() == baseline
    second = copy.deepcopy(first)
    second['metadata']['version'] += 1
    commit(root, personal, second)
    with pytest.raises(ValueError, match='旧版本'):
        commit(root, personal, first)
    content.deactivate(first['archive']['id'])
    with pytest.raises(ValueError, match='旧版本'):
        commit(root, personal, first)
    same_base = package('3301')
    raw = (SOURCE / 'stories' / f"{same_base['archive']['id']}.json").read_bytes()
    commit(root, personal, same_base, raw=raw)
    different = copy.deepcopy(same_base)
    different['archive']['title'] = '同版本基础改稿'
    with pytest.raises(ValueError, match='基础内容不同'):
        commit(root, personal, different)


def test_import_cannot_claim_official_origin_or_reserved_removed_id(library):
    root, personal = library
    data = package()
    data['metadata']['origin'] = 'builtin'
    data['metadata']['delivery'] = 'downloaded'
    imported = stories.StoryService().import_package(data)
    assert imported['origin'] == 'imported' and imported['delivery'] is None
    with pytest.raises(ValueError, match='ID_CONFLICT'):
        commit(root, personal, data)
    (personal / f"{data['archive']['id']}.json").unlink()
    commit(root, personal, data)
    content.deactivate(data['archive']['id'])
    with pytest.raises(ValueError, match='官方下载'):
        stories.StoryService().import_package(data)
    assert list(personal.iterdir()) == []


def test_native_validator_bounds_paths_and_rejects_unmapped_images(library):
    root, personal = library
    sid, version, digest, directory = pack(root, package())
    assert content.validate_package(str(directory), digest)['id'] == sid
    with pytest.raises(ValueError, match='目录无效'):
        content.validate_package(str(personal), digest)
    images = directory / 'images'
    images.mkdir(exist_ok=True)
    (images / 'unmapped.webp').write_bytes(b'not-a-webp')
    with pytest.raises(ValueError, match='清单不同'):
        content.activate(sid, version, digest, str(personal))
    assert content.read_registry()['stories'] == {}


def test_incomplete_incompatible_or_corrupt_pack_does_not_hide_base(library):
    root, personal = library
    sid, version, digest, directory = pack(root, package(), engine=2)
    with pytest.raises(ValueError, match='引擎'):
        content.activate(sid, version, digest, str(personal))
    (directory / 'complete.json').unlink()
    with pytest.raises(OSError):
        content.activate(sid, version, digest, str(personal))
    assert len(stories.list_stories()) == 3
    (root / 'registry.json').write_text('corrupt')
    assert len(stories.list_stories()) == 3
    with pytest.raises(ValueError):
        content.read_registry()
    assert (root / 'registry.json').read_text() == 'corrupt'


def test_namespace_lock_allows_only_one_personal_or_official_winner(library):
    root, personal = library
    data = package()
    sid, version, digest, _ = pack(root, data)
    barrier = threading.Barrier(2)
    def install():
        barrier.wait()
        try:
            content.activate(sid, version, digest, str(personal))
            return 'official'
        except ValueError:
            return 'rejected'
    def importing():
        barrier.wait()
        try:
            stories.StoryService().import_package(data)
            return 'personal'
        except ValueError:
            return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.submit(install), pool.submit(importing)
        results = [left.result(), right.result()]
    assert results.count('rejected') == 1
    assert content.owns_id(sid) != (personal / f'{sid}.json').exists()


@pytest.mark.parametrize('raw', [b'{"version":1,"version":2}', b'{"value":NaN}', b'[]'])
def test_strict_content_json_rejects_duplicate_keys_and_invalid_numbers(raw):
    with pytest.raises(ValueError):
        strict_json(raw)
