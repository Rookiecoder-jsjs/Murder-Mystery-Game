"""Content and information-boundary regressions, using the actual archives."""
import json
from pathlib import Path

import pytest

from app.domain.models import StoryArchive
from app.core.phases import GamePhase
from app.services.session_service import GameSession
from tests.test_session_service import StubRoleplayClient

STORIES = sorted((Path(__file__).parents[1] / 'stories').glob('*.json'))

@pytest.mark.parametrize('path', STORIES, ids=lambda p: p.stem[:8])
def test_every_archive_is_reachable_and_staged(path):
    archive = StoryArchive.from_dict(json.loads(path.read_text()))
    archive.validate(require_script=True)
    human = next(c for c in archive.characters if c.id != archive.case.true_killer)
    session = GameSession(archive, human.id, StubRoleplayClient(), 'quick')
    session.game.set_phase(GamePhase.INVESTIGATION)
    counts = []
    for round_no in (1, 2, 3):
        session.game.state.round = round_no
        found = 0
        while session.get_investigation_options():
            session.investigate()
            found += 1
        counts.append(found)
        if round_no < 3:
            assert any(c.id not in session.game.state.player_states[human.id].known_clues
                       and not c.reveal_to_all for c in archive.clues)
    visible = {c.id for c in session.game.get_player_clues(human.id)} | {
        c.id for c in session.game.get_revealed_clues()}
    assert visible == {c.id for c in archive.clues}
    assert all(counts), counts
    assert human.self_knowledge and human.objectives


def test_cycles_and_missing_dependencies_rejected(sample_archive):
    a, b = sample_archive.clues[:2]
    a.required_clue_id, b.required_clue_id = b.id, a.id
    with pytest.raises(ValueError, match='循环'):
        sample_archive.validate()
    a.required_clue_id = 'missing'
    with pytest.raises(ValueError, match='不存在'):
        sample_archive.validate()


def test_duplicate_ids_and_killer_mismatch_rejected(sample_archive):
    sample_archive.clues[1].id = sample_archive.clues[0].id
    with pytest.raises(ValueError, match='重复'):
        sample_archive.validate()


def test_safe_player_script_never_falls_back_to_author_secret(sample_archive):
    char = sample_archive.characters[1]
    char.secret = '作者知道：Alice 是凶手'
    char.backstory = '作者全知信息'
    char.alibi = '全知时间线'
    char.self_knowledge = '我在大厅等人，曾隐瞒一笔债务。'
    char.objectives = ['找出凶手', '解释自己的行踪']
    session = GameSession(sample_archive, char.id, StubRoleplayClient())
    info = session.get_player_info()
    assert info['role_script'] == char.self_knowledge
    assert '作者' not in json.dumps(info, ensure_ascii=False)
    assert all('role_script' not in c for c in session.get_all_characters())
    char.self_knowledge = ''
    assert '作者' not in json.dumps(session.get_player_info(), ensure_ascii=False)


def test_initial_knowledge_belongs_to_each_role(sample_archive):
    session = GameSession(sample_archive, 'char_2', StubRoleplayClient())
    for char in sample_archive.characters:
        actual = session.game.get_player_clues(char.id)
        assert {c.id for c in actual} == set(char.clues)
        assert all(c.holder_id == char.id for c in actual)
    assert session.game.state.investigation_count == 0


def test_presenting_evidence_requires_ownership(sample_archive):
    session = GameSession(sample_archive, 'char_2', StubRoleplayClient())
    session.game.set_phase(GamePhase.DISCUSSION)
    from app.core.errors import GameError as HTTPException
    with pytest.raises(HTTPException):
        session.validate_discussion('char_3', ['clue_a'])
    assert not session.game.get_clue('clue_a').reveal_to_all
    session.validate_discussion('char_3', ['clue_b'])
    session.game.present_clues('char_2', ['clue_b'])
    assert 'clue_b' in {c.id for c in session.game.get_revealed_clues()}


def test_direct_question_only_invokes_target(sample_archive):
    import asyncio
    client = StubRoleplayClient()
    session = GameSession(sample_archive, 'char_2', client)
    session.game.set_phase(GamePhase.DISCUSSION)
    replies = asyncio.run(session.player_speak_collect('请解释证词', 'char_3', ['clue_b']))
    assert [r['speaker'] for r in replies] == ['Carol']
    generation = next(call for call in client.calls
                      if call['tool_choice']['function']['name'] == 'submit_statement')
    context = json.loads(generation['messages'][1]['content'])
    assert 'clue_b' in {c['id'] for c in context['clues']}
    restored = GameSession.from_snapshot(session.to_snapshot('g'), sample_archive, client)
    assert 'clue_b' in {c.id for c in restored.game.get_revealed_clues()}


@pytest.mark.parametrize('path', STORIES, ids=lambda p: p.stem[:8])
@pytest.mark.parametrize('mode', ['classic', 'quick'])
def test_complete_flow_for_every_playable_role(path, mode):
    import asyncio
    raw = json.loads(path.read_text())
    async def run():
        for character in raw['characters']:
            if character['id'] == raw['case']['true_killer']:
                continue
            archive = StoryArchive.from_dict(raw)
            session = GameSession(archive, character['id'], StubRoleplayClient(), mode)
            await session.player_introduce_async('我来调查。')
            session.advance_phase()
            for round_no in range(1, 4 if mode == 'quick' else 2):
                while session.game.get_available_clues(character['id']):
                    session.investigate()
                session.advance_phase()
                target = next(iter(session.ai_characters))
                await session.player_speak_collect('请解释案发行踪。', target)
                if mode == 'quick' and round_no < 3:
                    session.start_next_round()
            visible = {c.id for c in session.game.get_player_clues(character['id'])} | {
                c.id for c in session.game.get_revealed_clues()}
            assert visible == {c.id for c in archive.clues}
            session.start_voting()
            # NPCs all disagree or abstain: the player's earned answer still counts.
            for ai in session.ai_characters.values():
                ai.get_vote = lambda **kw: ('', '')
            result = await session.vote_async(session._char_name(archive.case.true_killer))
            assert result['game_ended'] and result['winner'] == 'good'
            restored = GameSession.from_snapshot(session.to_snapshot('saved'), StoryArchive.from_dict(raw), StubRoleplayClient())
            assert restored.get_reveal_info()['winner'] == 'good'
    asyncio.run(run())


def test_known_spoilers_are_only_in_author_notes():
    snow = json.loads(next(p for p in STORIES if p.stem.startswith('b394')).read_text())
    sheet = snow['characters'][0]['self_knowledge']
    assert '白秀珠' not in sheet
    assert '当晚九时后，沈万山独自进入' not in snow['case']['background']
    assert '白俄流亡贵族' not in snow['case']['background']
    darkroom = json.loads(next(p for p in STORIES if p.stem.startswith('4386')).read_text())
    assert all('时间线：' not in c['content'] for c in darkroom['clues'])


def test_new_stories_require_scripts_and_each_release_round(sample_archive):
    with pytest.raises(ValueError, match='本人知识'):
        sample_archive.validate(require_script=True)


def test_round_gate_survives_restore(sample_archive):
    session = GameSession(sample_archive, 'char_2', StubRoleplayClient(), 'quick')
    session.game.set_phase(GamePhase.INVESTIGATION)
    snapshot = session.to_snapshot('old')
    restored = GameSession.from_snapshot(snapshot, sample_archive, StubRoleplayClient())
    assert all(restored.game._release_rounds[c.id] == 1
               for c in restored.game.get_available_clues('char_2'))


def test_initial_clue_error_identifies_the_exact_ownership_conflict(sample_archive):
    """Repair feedback must identify the bad reference without granting scene evidence."""
    import copy
    archive = copy.deepcopy(sample_archive)
    character = archive.characters[0]
    clue = archive.clues[0]
    clue.holder_id = 'scene'
    character.clues = [clue.id]
    with pytest.raises(ValueError) as error:
        archive.validate()
    message = str(error.value)
    assert f'{character.id}.clue_ids' in message
    assert f'{clue.id}(holder_id=scene)' in message
    assert '不要为绕过校验改变线索归属' in message
    assert clue.holder_id == 'scene'
