"""Catalog contract, update isolation, and playable original cases (no network)."""
import asyncio
import copy
import json
import uuid

import pytest
from pydantic import ValidationError

from app.api.schemas import CreateGameRequest
from app.domain.models import StoryArchive
from app.services import story_catalog as catalog, story_service as stories
from app.services.session_service import GameSession, SessionManager, JsonFileSessionStore
from tests.test_session_service import StubRoleplayClient


def package():
    name = json.loads((catalog.CONTENT_DIR / 'manifest.json').read_text())['packages'][0]
    result = json.loads((catalog.CONTENT_DIR / name).read_text())
    result['archive']['id'] = str(uuid.uuid4())
    result['metadata']['version'] = 1
    return result


@pytest.mark.parametrize('count', [3, 4, 5, 6, 7, 8, None])
def test_character_count_contract(count):
    assert CreateGameRequest(topic='原创案件', character_count=count).character_count == count


@pytest.mark.parametrize('count', [2, 9, True, '5', 4.5])
def test_reject_invalid_character_count(count):
    with pytest.raises(ValidationError):
        CreateGameRequest(topic='原创案件', character_count=count)
    with pytest.raises(ValueError):
        catalog.validate_character_count(count)


def test_catalog_lists_safe_metadata_and_never_calls_models(tmp_path, monkeypatch):
    monkeypatch.setattr(stories, 'STORIES_DIR', str(tmp_path))
    monkeypatch.setattr(stories, 'create_deepseek_client', lambda: pytest.fail('opening catalog must stay offline'))
    items = stories.list_stories()
    assert [item['num_characters'] for item in items] == [3, 5, 7]
    assert all(item['origin'] == 'builtin' and item['version'] >= 1 for item in items)
    assert not any(key in json.dumps(items) for key in ('true_killer', 'self_knowledge', 'solution', 'story_content'))
    service = stories.StoryService()
    for item in items:
        assert service.get_playable_story(item['id']).title == item['title']
        assert service.remove_story(item['id']) is False


def test_bundled_artwork_is_complete_offline_and_imports_cannot_claim_it():
    from app.services.image_service import normalize_portraits
    for archive in catalog.builtin_stories():
        urls = [catalog.story_info(archive)['cover_url'],
                *[c.portrait_url for c in archive.characters]]
        for url in urls:
            relative = url.removeprefix('/assets/story-library/')
            assert url.startswith('/assets/story-library/')
            assert (catalog.ARTWORK_DIR / relative).is_file()
            assert (catalog.ARTWORK_DIR / relative).read_bytes()[:4] == b'RIFF'
        normalize_portraits(archive)
        assert [c.portrait_url for c in archive.characters] == urls[1:]
        frozen = StoryArchive.from_dict(archive.to_dict())
        assert frozen.catalog['cover_url'] == urls[0]
        assert [c.portrait_url for c in frozen.characters] == urls[1:]
    data = package()
    data['metadata']['cover_url'] = 'https://untrusted.example/cover.webp'
    data['archive']['characters'][0]['portrait_url'] = '/assets/story-library/fake.webp'
    imported = catalog.parse_package(data)
    assert catalog.story_info(imported)['cover_url'] == ''
    assert all(not c.portrait_url for c in imported.characters)


@pytest.mark.parametrize('artwork', [{'cover': '../escape.webp'}, {'portraits': {'missing': 'char_1-v1.webp'}}, {'portraits': []}, {'retained_files': ['../old.webp']}])
def test_bundled_artwork_rejects_invalid_paths_and_roles(artwork):
    archive = catalog.parse_package(package())
    with pytest.raises(ValueError, match='配图'):
        catalog._apply_builtin_artwork(archive, artwork)


def test_import_upgrade_preserves_active_and_restored_game(tmp_path, monkeypatch):
    monkeypatch.setattr(stories, 'STORIES_DIR', str(tmp_path))
    service = stories.StoryService()
    first = package()
    info = service.import_package(first)
    assert info['origin'] == 'imported'
    assert service.import_package(first) == info  # lost-ack retry is idempotent
    manager = SessionManager(StubRoleplayClient(), service, JsonFileSessionStore(str(tmp_path / 'sessions')))
    archive = service.get_playable_story(info['id'])
    gid, old_game = manager.create_session(archive=archive)
    snapshot = old_game.to_snapshot(gid)
    upgraded = copy.deepcopy(first)
    upgraded['metadata']['version'] = 2
    upgraded['archive']['title'] = '修订后的新标题'
    service.import_package(upgraded)
    assert service.get_playable_story(info['id']).title == '修订后的新标题'
    assert old_game.archive.title == first['archive']['title']
    restored = GameSession.from_snapshot(snapshot, StoryArchive.from_dict(snapshot['archive']), StubRoleplayClient())
    restarted = SessionManager(StubRoleplayClient(), service, manager._store)
    assert restarted.load_all_persisted() == 1
    assert restarted.get(gid).archive.catalog['version'] == 1
    assert restored.archive.catalog['version'] == 1
    assert restored.archive.title == first['archive']['title']
    with pytest.raises(ValueError, match='更高版本'):
        service.import_package(first)
    assert service.get_playable_story(info['id']).catalog['version'] == 2


def test_builtin_upgrade_only_changes_new_openings(tmp_path, monkeypatch):
    source = catalog.CONTENT_DIR
    for path in source.glob('*.json'):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(catalog, 'CONTENT_DIR', tmp_path)
    original = catalog.builtin_stories()[0]
    game = GameSession(original, original.characters[1].id, StubRoleplayClient())
    path = tmp_path / f'{original.id}.json'
    revised = json.loads(path.read_text())
    revised['metadata']['version'] = original.catalog['version'] + 1
    revised['archive']['title'] = '内置新版'
    path.write_text(json.dumps(revised))
    assert stories.load_story(original.id).catalog['version'] == original.catalog['version'] + 1
    assert game.archive.title == original.title
    assert game.archive.catalog['version'] == original.catalog['version']


@pytest.mark.parametrize('invalid', ['version', 'path', 'holder', 'quote', 'cycle', 'origin'])
def test_package_rejection_and_untrusted_origin(invalid):
    data = package()
    if invalid == 'version':
        data['metadata']['version'] = 0
    elif invalid == 'path':
        data['archive']['id'] = '../escape'
    elif invalid == 'holder':
        data['archive']['clues'][0]['holder_id'] = 'missing'
    elif invalid == 'quote':
        data['archive']['solution'][0]['evidence'][0]['quote'] = '不存在的证据'
    elif invalid == 'cycle':
        data['archive']['clues'][0]['required_clue_id'] = 'clue_1'
    else:
        data['metadata']['origin'] = 'builtin'
        data['archive']['production'] = {'status': 'ready', 'origin': 'builtin'}
        assert catalog.parse_package(data).catalog['origin'] == 'imported'
        return
    with pytest.raises(ValueError):
        catalog.parse_package(data)


def test_import_cannot_overwrite_builtin(tmp_path, monkeypatch):
    monkeypatch.setattr(stories, 'STORIES_DIR', str(tmp_path))
    data = package()
    data['archive']['id'] = catalog.builtin_stories()[0].id
    with pytest.raises(ValueError, match='不能覆盖'):
        stories.StoryService().import_package(data)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('mode', ['quick', 'classic'])
def test_original_case_all_player_roles_reach_reveal(index, mode):
    original = catalog.builtin_stories()[index]
    async def play():
        for player in original.characters:
            if player.is_killer:
                continue
            archive = StoryArchive.from_dict(original.to_dict())
            session = GameSession(archive, player.id, StubRoleplayClient(), mode=mode)
            await session.player_introduce_async('')
            session.advance_phase()
            assert len(session.ai_characters) == len(archive.characters) - 1
            for round_number in range(1, 4) if mode == 'quick' else [1]:
                while session.game.get_available_clues(player.id):
                    options = session.get_investigation_options()
                    session.investigate(options[0]['id'] if options else None)
                session.advance_phase()
                await session.player_speak_collect('请说明本轮你知道的情况。')
                if mode == 'quick' and round_number < 3:
                    session.start_next_round()
            # All authored conclusions are backed by discoverable scene evidence.
            assert {clue.id for clue in archive.clues} <= {clue.id for clue in session.game.get_revealed_clues()}
            session.start_voting()
            killer = session.game.get_character(session.game.killer_id)
            await session.vote_async(killer.name)
            assert session.game.state.phase == 'reveal'
            result = session.get_reveal_info()
            assert [d['conclusion'] for d in result['deductions']] == [d['conclusion'] for d in original.solution]
    asyncio.run(play())


def test_specified_count_is_checked_before_review(monkeypatch):
    from tests.test_story_service import CASE_DATA
    drafts = [copy.deepcopy(CASE_DATA), copy.deepcopy(CASE_DATA)]
    drafts[1]['characters'].append({'id': 'char_4', 'name': '第四人', 'self_knowledge': '我在门房。', 'objectives': ['核对经历']})
    calls = []
    def generate(prompt, *args, **kwargs):
        calls.append(prompt)
        return json.dumps(drafts.pop(0))
    reviews = []
    monkeypatch.setattr(stories, 'generate_story_text', generate)
    monkeypatch.setattr(stories, 'review_story_consistency', lambda data, *a, **k: reviews.append(data))
    data = stories.generate_story('四人故事', None, character_count=4)
    assert len(data['characters']) == 4
    assert len(calls) == 2 and '恰好4名' in calls[0]
    assert len(reviews) == 1
