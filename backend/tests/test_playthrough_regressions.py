"""Counterexamples captured in the 2026-10-02 browser playthrough."""
import copy
import json
from pathlib import Path

import pytest

from app.agents.roleplay_character import RoleplayCharacter
from app.core.phases import GamePhase
from app.core.roleplay_protocol import InvalidStatement, validate_statement, speech_segments
from app.domain.models import StoryArchive
from app.domain.context import DiscussionEvent
from app.services.context_service import ContextAssembler
from app.services import story_service as ss, image_service as images
from tests.test_roleplay_character import SequenceClient, _Message, _ToolCall

STORY_PATH = Path(__file__).parents[1] / 'stories/bf5d01d5-94b0-4b9b-a207-d95d4433a91e.json'


def pawn():
    return StoryArchive.from_dict(json.loads(STORY_PATH.read_text()))


def role_context(archive, character_id):
    character = next(c for c in archive.characters if c.id == character_id)
    return character, ContextAssembler.assemble(character=character, phase=GamePhase.DISCUSSION,
        case=archive.case, other_chars=archive.characters)


def test_recorded_compound_summary_cannot_mask_extra_actions():
    _, context = role_context(pawn(), 'char_5')
    # The old validator accepted a summary that omitted the return after police arrived.
    data = {'speech': '枪响前我在前堂擦木柜。枪一响我往门口退，巡捕来了我才回屋。',
            'claims': [{'text': '枪响前赵大宝擦木柜，枪响后往门口退，未进入柜台内。',
                        'kind': 'observed', 'source_ids': ['self:knowledge']}], 'corrections': []}
    with pytest.raises(InvalidStatement, match='逐字摘自'):
        validate_statement(json.dumps(data), context)


def test_old_positive_review_without_whole_speech_coverage_is_rejected():
    character, context = role_context(pawn(), 'char_5')
    speech = '我在前堂柜台外擦木柜，后来退到门口，巡捕到场后才回屋。'
    data = {'speech': speech, 'claims': [{'text': speech, 'kind': 'observed',
            'source_ids': ['self:knowledge']}], 'corrections': []}
    # This genuine quote supports only the first clause, just like the recorded bad review.
    response = {'valid': True, 'issues': [], 'checks': [{'claim_index': 0,
        'supported': True, 'source_id': 'self:knowledge', 'quote': '我在前堂柜台外擦木柜'}]}
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps(response), 'check_statement')])])
    role = RoleplayCharacter(character, client)
    with pytest.raises(InvalidStatement, match='全部分句'):
        role._review_statement(json.dumps(data), context, 1)
    submitted = json.loads(client.calls[0]['messages'][1]['content'])
    assert submitted['speech_segments'] == speech_segments(speech)
    assert len(submitted['speech_segments']) == 3


def test_unregistered_factual_clause_cannot_pass_segment_review():
    character, context = role_context(pawn(), 'char_5')
    speech = '我在前堂柜台外擦木柜。'
    response = {'valid': True, 'issues': [], 'checks': [], 'segments': [{
        'segment_index': 0, 'supported': True, 'non_factual': False,
        'source_id': 'self:knowledge', 'quote': '我在前堂柜台外擦木柜', 'unsupported_details': []}]}
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps(response), 'check_statement')])])
    with pytest.raises(InvalidStatement, match='缺少对应陈述'):
        RoleplayCharacter(character, client)._review_statement(json.dumps({
            'speech': speech, 'claims': [], 'corrections': []}), context, 1)


def test_cover_is_separate_from_facts_and_cannot_invent_ledger_excuse():
    character, context = role_context(pawn(), 'char_2')
    assert context.payload()['role']['cover_story']['kind'] == 'cover'
    raw = {'speech': '缺的账页是周掌柜拿走的。', 'claims': [{
        'text': '缺的账页是周掌柜拿走的。', 'kind': 'cover', 'source_ids': ['self:knowledge']}], 'corrections': []}
    with pytest.raises(InvalidStatement, match='self:cover'):
        validate_statement(json.dumps(raw), context)
    raw['claims'][0]['source_ids'] = ['self:cover']
    assert validate_statement(json.dumps(raw), context)
    reply = RoleplayCharacter._clarification(context, '账页为什么缺失？')
    assert '私吞' not in reply and '刺入' not in reply
    assert '账页是周掌柜拿走' in reply


def test_legacy_mixed_truth_and_lies_are_not_personal_facts():
    archive = pawn()
    char = archive.characters[4]
    char.cover_story = ''
    char.self_knowledge = '【你的经历】我在当铺做工。\n【你的案发行动与对外说辞】真：我声称看见黑影。假：实际没看见。'
    _, context = role_context(archive, char.id)
    sources = {s.source_id: s for s in context.sources}
    assert '黑影' not in sources['self:knowledge'].text
    assert sources['self:legacy_alibi'].kind == 'document'
    assert context.payload()['role']['can_use_cover'] is False


def test_lin_fallback_still_answers_his_letter_without_inventing_arrival():
    _, context = role_context(pawn(), 'char_4')
    reply = RoleplayCharacter._clarification(context, '你写密信的落款十一点，是你到店时间吗？')
    assert '我亲笔写了' in reply
    assert '不代表我到店时间' in reply
    assert reply.claims and reply.claims[0].kind == 'observed'


def test_every_pawn_deduction_has_discoverable_exact_evidence():
    archive = pawn()
    archive.validate(require_script=True, require_solution=True)
    assert '头部中弹' not in archive.case.background
    assert '没有弹孔' in archive.clues[1].content
    assert next(c for c in archive.clues if c.id == 'clue_14').type == 'physical'
    for deduction in archive.solution:
        assert all(archive.release_rounds()[r['clue_id']] <= 3 for r in deduction['evidence'])
    archive.solution[0]['evidence'][0]['quote'] = '结局才出现的烟灰鉴定'
    with pytest.raises(ValueError, match='原文'):
        archive.validate()


def test_archive_without_solution_is_legacy_only():
    archive = pawn()
    archive.solution = []
    archive.validate()
    with pytest.raises(ValueError, match='solution'):
        archive.validate(require_solution=True)


def test_solution_never_enters_role_context():
    archive = pawn()
    archive.solution[0]['conclusion'] = 'AUTHOR_ONLY_SOLUTION'
    for c in archive.characters:
        _, context = role_context(archive, c.id)
        assert 'AUTHOR_ONLY_SOLUTION' not in context.payload_json


def test_saved_archives_do_not_trigger_online_review_or_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, 'STORIES_DIR', str(tmp_path / 'stories'))
    archive = pawn()
    monkeypatch.setattr(ss, 'load_story', lambda _id: copy.deepcopy(archive))
    def unexpected(*args):
        raise AssertionError('成品读取不能触发在线制作')
    monkeypatch.setattr(ss, 'review_story_consistency', unexpected)
    for _ in range(2):
        service = ss.StoryService()
        monkeypatch.setattr(service, '_schedule_portraits', unexpected)
        assert service.get_playable_story(archive.id).id == archive.id
    assert not list(tmp_path.rglob('*.json'))


def test_missing_portraits_clear_stale_urls_and_recover_local_assets(monkeypatch, tmp_path):
    archive = pawn()
    monkeypatch.setattr(images, 'PORTRAITS_DIR', tmp_path)
    directory = tmp_path / archive.id
    directory.mkdir()
    (directory / 'char_1.jpg').write_bytes(b'test-image')
    images.normalize_portraits(archive)
    assert archive.characters[0].portrait_url.endswith('char_1.jpg')
    assert all(not c.portrait_url for c in archive.characters[1:])


def test_segment_protocol_has_only_one_source_of_displayed_text():
    from app.core.roleplay_protocol import canonical_statement
    _, context = role_context(pawn(), 'char_4')
    data = {'segments': [
        {'text': '我亲笔写了邀请周厚坤午夜到后巷验货的密信。', 'kind': 'observed', 'source_ids': ['self:knowledge']},
        {'text': '到店时刻我无法确认。', 'kind': 'aside', 'source_ids': []},
    ], 'corrections': []}
    canonical = canonical_statement(json.dumps(data))
    result = validate_statement(canonical, context)
    assert result == ''.join(s['text'] for s in data['segments'])
    assert len(result.claims) == 1
    # An extra, unregistered prose draft cannot override the rendered segments.
    data['speech'] = '我十一点到店。'
    with pytest.raises(InvalidStatement):
        canonical_statement(json.dumps(data))


def test_portrait_repair_merges_assets_without_reverting_story_edits(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, 'STORIES_DIR', str(tmp_path / 'stories'))
    monkeypatch.setattr(images, 'PORTRAITS_DIR', tmp_path / 'portraits')
    archive = pawn()
    ss.save_story(archive)
    service = ss.StoryService()
    def generate(old):
        current = ss.load_story(old.id)
        current.clues[0].content += '期间修正的案情'
        ss.save_story(current)
        old.characters[0].portrait_url = 'https://example.org/new-portrait.png'
        return 1
    monkeypatch.setattr(service.portrait_service, 'generate_for_archive', generate)
    service._generate_portraits_background(archive)
    current = ss.load_story(archive.id)
    assert current.clues[0].content.endswith('期间修正的案情')
    assert current.characters[0].portrait_url == 'https://example.org/new-portrait.png'


def test_portrait_completion_cannot_resurrect_a_deleted_story(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, 'STORIES_DIR', str(tmp_path / 'stories'))
    monkeypatch.setattr(images, 'PORTRAITS_DIR', tmp_path / 'portraits')
    archive = pawn()
    ss.save_story(archive)
    service = ss.StoryService()
    def generate(old):
        ss.delete_story(old.id)
        old.characters[0].portrait_url = 'https://example.org/new-portrait.png'
        return 1
    monkeypatch.setattr(service.portrait_service, 'generate_for_archive', generate)
    service._generate_portraits_background(archive)
    assert ss.load_story(archive.id) is None


def test_redundant_document_citation_is_removed_without_promoting_it():
    from app.core.roleplay_protocol import narrow_statement_sources
    archive = pawn()
    context = ContextAssembler.assemble(character=archive.characters[3], phase=GamePhase.DISCUSSION,
        case=archive.case, known_clues=[archive.clues[2]])
    data = {'speech': '信是我亲笔写的。', 'claims': [{'text': '信是我亲笔写的。',
        'kind': 'observed', 'source_ids': ['self:knowledge', 'clue:clue_3']}], 'corrections': []}
    normalized = narrow_statement_sources(json.dumps(data), context)
    assert validate_statement(normalized, context).claims[0].source_ids == ('self:knowledge',)
    data['claims'][0]['source_ids'] = ['clue:clue_3']
    with pytest.raises(InvalidStatement, match='亲历事实'):
        validate_statement(narrow_statement_sources(json.dumps(data), context), context)
    data['claims'][0]['source_ids'] = ['self:knowledge', 'inaccessible']
    with pytest.raises(InvalidStatement, match='不可见'):
        validate_statement(narrow_statement_sources(json.dumps(data), context), context)


def test_deepseek_review_uses_independent_model_but_custom_provider_keeps_compatibility(monkeypatch):
    from app.core.config import RoleplayConfig
    monkeypatch.delenv('ROLEPLAY_REVIEW_MODEL', raising=False)
    monkeypatch.setenv('ROLEPLAY_BASE_URL', 'https://api.deepseek.com/v1')
    assert RoleplayConfig.from_env().review_model_name == 'deepseek-v4-pro'
    monkeypatch.setenv('ROLEPLAY_BASE_URL', 'http://localhost:9999/v1')
    monkeypatch.setenv('ROLEPLAY_MODEL', 'local-model')
    assert RoleplayConfig.from_env().review_model_name == 'local-model'


def test_yi_shi_hesitation_is_not_an_invented_clock_time():
    _, context = role_context(pawn(), 'char_2')
    raw = {'speech': '老朽一时不便细说。', 'claims': [], 'corrections': []}
    assert validate_statement(json.dumps(raw), context) == raw['speech']
    raw['speech'] = '我在凌晨一时走进柜台。'
    raw['claims'] = [{'text': raw['speech'], 'kind': 'observed', 'source_ids': ['self:knowledge']}]
    with pytest.raises(InvalidStatement, match='明确时间'):
        validate_statement(json.dumps(raw), context)


def test_reviewer_can_correct_a_visible_citation_and_persists_actual_provenance():
    archive = pawn()
    character, context = role_context(archive, 'char_4')
    speech = '我没有看见柜台内的凶手。'
    raw = json.dumps({'speech': speech, 'claims': [{'text': speech, 'kind': 'observed',
        'source_ids': ['case:background']}], 'corrections': []})
    response = {'valid': True, 'issues': [], 'segments': [{'segment_index': 0, 'supported': True,
        'non_factual': False, 'source_id': 'self:knowledge', 'quote': speech, 'unsupported_details': []}]}
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps(response), 'check_statement')])])
    role = RoleplayCharacter(character, client)
    assert role._review_statement(raw, context, 1)[0].source_ids == ('self:knowledge',)


def test_document_description_downgrades_to_report_but_not_personal_arrival():
    from app.core.roleplay_protocol import narrow_statement_sources
    archive = pawn()
    context = ContextAssembler.assemble(character=archive.characters[3], phase=GamePhase.DISCUSSION,
        case=archive.case, known_clues=[archive.clues[2]])
    speech = '信上落款十一点。'
    data = {'speech': speech, 'claims': [{'text': speech, 'kind': 'observed',
        'source_ids': ['clue:clue_3']}], 'corrections': []}
    assert validate_statement(narrow_statement_sources(json.dumps(data), context), context).claims[0].kind == 'reported'
    data['speech'] = data['claims'][0]['text'] = '我十一点到店。'
    with pytest.raises(InvalidStatement, match='亲历事实'):
        validate_statement(narrow_statement_sources(json.dumps(data), context), context)


def test_clause_split_keeps_document_quote_and_attribution_together():
    assert speech_segments('残页上「钱经手，私取银元二百」正是我记的。我无法确认时间。') == [
        '残页上「钱经手，私取银元二百」正是我记的。', '我无法确认时间。']


def test_grounded_fallback_answers_ledger_question_without_reprinting_exhibit():
    _, context = role_context(pawn(), 'char_2')
    reply = RoleplayCharacter._clarification(context, '缺的账页是谁拿走的？')
    assert reply == '缺的账页是周掌柜拿走的。'
    assert reply.claims[0].kind == 'cover'


def test_review_gets_uncertainty_scope_without_hiding_any_clauses():
    from app.core.roleplay_protocol import speech_sentence_contexts
    character, context = role_context(pawn(), 'char_4')
    speech = '是谁下的药，我不知道。'
    assert speech_sentence_contexts(speech) == [speech, speech]
    response = {'valid': True, 'issues': [], 'segments': [
        {'segment_index': i, 'supported': True, 'non_factual': True,
         'source_id': '', 'quote': '', 'unsupported_details': []} for i in range(2)]}
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps(response), 'check_statement')])])
    role = RoleplayCharacter(character, client)
    assert role._review_statement(json.dumps({'speech': speech, 'claims': [], 'corrections': []}), context, 1) == ()
    request = json.loads(client.calls[0]['messages'][1]['content'])
    assert request['sentence_contexts'] == [speech, speech]
    assert request['speech_segments'] == ['是谁下的药，', '我不知道。']


def test_unknown_tail_cannot_hide_unsupported_action():
    from app.core.roleplay_protocol import speech_sentence_contexts
    character, context = role_context(pawn(), 'char_4')
    speech = '我退到门口，我不知道谁下药。'
    assert speech_sentence_contexts(speech) == [speech, speech]
    response = {'valid': True, 'issues': [], 'segments': [
        {'segment_index': 0, 'supported': False, 'non_factual': False,
         'source_id': '', 'quote': '', 'unsupported_details': ['退到门口无依据']},
        {'segment_index': 1, 'supported': True, 'non_factual': True,
         'source_id': '', 'quote': '', 'unsupported_details': []}]}
    client = SequenceClient([_Message(tool_calls=[_ToolCall(json.dumps(response), 'check_statement')])])
    with pytest.raises(InvalidStatement, match='无依据'):
        RoleplayCharacter(character, client)._review_statement(json.dumps({
            'speech': speech, 'claims': [], 'corrections': []}), context, 1)


def test_fallback_does_not_use_exhibit_keywords_for_unrelated_question():
    archive = pawn()
    character = next(c for c in archive.characters if c.id == 'char_4')
    context = ContextAssembler.assemble(character=character, phase=GamePhase.DISCUSSION,
        case=archive.case, known_clues=[archive.clues[0]],
        events=(DiscussionEvent('q', 1, 'char_1', '沈默', '提问', presented_clue_ids=('clue_1',)),), current_event_id='q')
    reply = RoleplayCharacter._clarification(context, 'Where were you when the noise occurred?')
    assert '密信' not in reply and '亲笔' not in reply
    assert '无法确认' in reply
    assert reply.claims and all(c.kind == 'reported' for c in reply.claims)


def test_fallback_acknowledges_footprints_instead_of_repeating_killer_alibi():
    archive = pawn()
    character = next(c for c in archive.characters if c.id == 'char_2')
    clue = next(c for c in archive.clues if c.id == 'clue_14')
    context = ContextAssembler.assemble(character=character, phase=GamePhase.DISCUSSION,
        case=archive.case, known_clues=[clue],
        events=(DiscussionEvent('q', 1, 'char_1', '沈默', '提问', presented_clue_ids=('clue_14',)),), current_event_id='q')
    reply = RoleplayCharacter._clarification(context, '为什么这些鞋印证明你去过柜台？')
    assert '线索记载' in reply and '无法确认' in reply
    assert '一直在账房' not in reply and '刺入' not in reply
    assert all(c.kind == 'reported' for c in reply.claims)
