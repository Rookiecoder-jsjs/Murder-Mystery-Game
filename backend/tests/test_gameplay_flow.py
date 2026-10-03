"""Finished stories and local game actions must not wait on authoring models."""
import asyncio
import copy
import pytest
from unittest.mock import Mock

from app.core.phases import GamePhase
from app.domain.models import StoryArchive
from app.services import story_service as ss
from app.services.session_service import GameSession
from tests.test_session_service import StubRoleplayClient
from tests.test_story_service import CASE_DATA


def test_saved_story_cold_start_never_reviews_or_generates_assets(monkeypatch, tmp_path, sample_archive):
    monkeypatch.setattr(ss, "STORIES_DIR", str(tmp_path / "stories"))
    ss.save_story(sample_archive)
    review = Mock(side_effect=AssertionError("开局不得审稿"))
    monkeypatch.setattr(ss, "review_story_consistency", review)
    for _ in range(2):
        service = ss.StoryService()
        assets = Mock(side_effect=AssertionError("开局不得生成画像"))
        monkeypatch.setattr(service, "_schedule_portraits", assets)
        assert service.get_playable_story(sample_archive.id).title == sample_archive.title
        review.assert_not_called()
        assets.assert_not_called()


def test_generated_production_result_survives_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "STORIES_DIR", str(tmp_path / "stories"))
    monkeypatch.setattr(ss, "create_deepseek_client", lambda: None)
    monkeypatch.setattr(ss, "generate_story", lambda *args: copy.deepcopy(CASE_DATA))
    service = ss.StoryService()
    monkeypatch.setattr(service, "_schedule_portraits", lambda _: None)
    archive = service.create_story("制作元数据")
    restored = ss.load_story(archive.id)
    assert restored.production["status"] == "ready"
    assert restored.production["content_digest"] == service._review_key(restored)
    assert all(c.public_introduction and c.secret not in c.public_introduction
               for c in restored.characters if c.secret)
    legacy = restored.to_dict()
    legacy.pop("production")
    assert StoryArchive.from_dict(legacy).production == {}


def test_default_introductions_use_public_identity_without_model(sample_archive):
    client = StubRoleplayClient()
    session = GameSession(sample_archive, "char_2", client)
    response = asyncio.run(session.player_introduce_async("我的介绍"))
    assert not client.calls
    for intro in response["ai_introductions"]:
        character = next(c for c in sample_archive.characters if c.name == intro["speaker"])
        assert character.public_identity in intro["message"]
        assert character.secret not in intro["message"]
    assert asyncio.run(session.player_introduce_async("重复介绍")) == response


def test_supplemental_investigation_keeps_round_next_round_is_explicit(sample_archive):
    session = GameSession(sample_archive, "char_2", StubRoleplayClient(), mode="quick")
    session.game.set_phase(GamePhase.DISCUSSION)
    session.game.state.investigated_round = session.game.state.discussed_round = 1
    session.return_to_investigation()
    assert session.game.state.round == 1
    session.advance_phase()
    assert "next_round" in session.get_game_status()["available_actions"]
    session.start_next_round()
    assert session.game.state.round == 2


def test_player_verdict_is_local_advice_optional_and_restorable(sample_archive):
    client = StubRoleplayClient()
    session = GameSession(sample_archive, "char_2", client)
    session.game.set_phase(GamePhase.VOTING)
    result = asyncio.run(session.vote_async("Alice"))
    assert result["winner"] == "good" and result["game_ended"]
    assert not client.calls
    restored = GameSession.from_snapshot(session.to_snapshot("g"), copy.deepcopy(sample_archive), client)
    assert restored.get_reveal_info()["advice_state"] == "available"
    first = asyncio.run(restored.collect_ballot_advice())
    count = len(client.calls)
    assert count > 0 and first["advice_state"] == "completed"
    assert first["winner"] == "good"
    assert asyncio.run(restored.collect_ballot_advice()) == first
    assert len(client.calls) == count


def test_unfinished_production_is_not_published_or_opened(monkeypatch, tmp_path, sample_archive):
    monkeypatch.setattr(ss, 'STORIES_DIR', str(tmp_path / 'stories'))
    sample_archive.production = {'status': 'reviewing'}
    ss.save_story(sample_archive)
    assert sample_archive.id not in {story['id'] for story in ss.list_stories()}
    with pytest.raises(ValueError, match='尚未完成'):
        ss.StoryService().get_playable_story(sample_archive.id)


def test_authoring_route_simulation_does_not_publish_evidence(sample_archive):
    from app.domain.game_manager import GameManager
    flags = [c.reveal_to_all for c in sample_archive.clues]
    sample_archive.solution = [{'conclusion': '核对物证', 'evidence': [{'clue_id': 'clue_locked', 'quote': '内容'}]}]
    GameManager.validate_quick_evidence_routes(sample_archive)
    assert [c.reveal_to_all for c in sample_archive.clues] == flags


def test_optional_advice_keeps_pre_verdict_view_and_cannot_reopen_game(sample_archive):
    from app.core.errors import GameError
    session = GameSession(sample_archive, 'char_2', StubRoleplayClient())
    with pytest.raises(GameError):
        asyncio.run(session.collect_ballot_advice())
    session.game.set_phase(GamePhase.VOTING)
    asyncio.run(session.vote_async('Dave', 'terminal-action'))
    assert all(context['phase'] == 'voting' for context in session.pending_ballots['contexts'].values())
    snapshot = session.to_snapshot('g')
    restored = GameSession.from_snapshot(snapshot, copy.deepcopy(sample_archive), StubRoleplayClient())
    assert asyncio.run(restored.vote_async('Dave', 'terminal-action'))['winner'] == 'killer'
    with pytest.raises(GameError):
        restored.return_to_investigation()
    assert restored.game.state.phase == 'reveal'
