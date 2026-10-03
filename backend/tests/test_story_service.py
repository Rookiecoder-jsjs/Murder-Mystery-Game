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
        {"id": "char_1", "name": "张三", "self_knowledge": "我是真凶。", "objectives": ["隐瞒罪行"]},
        {"id": "char_2", "name": "李四", "self_knowledge": "我在大厅。", "objectives": ["调查凶手"]},
        {"id": "char_3", "name": "王五", "self_knowledge": "我在门口。", "objectives": ["说明经历"]},
    ],
    "clues": [{"id": f"clue_{i}", "content": f"物证{i}", "holder_id": "scene",
               "discovery_round": i, "lead": f"现场{i}"} for i in (1, 2, 3)],
    "truth": "真相叙述",
    "solution": [{"conclusion": "测试结论", "evidence": [{"clue_id": "clue_1", "quote": "物证1"}]}],
}


def _patch_llm(monkeypatch) -> None:
    """Short-circuit story generation so no LLM/network is involved."""
    monkeypatch.setattr(ss, "create_deepseek_client", lambda: None)
    monkeypatch.setattr(
        ss, "generate_story",
        lambda topic, client, show_reasoning=False: dict(CASE_DATA),
    )


def test_parse_preserves_punctuation_in_exact_evidence_quotes():
    import copy
    data = copy.deepcopy(CASE_DATA)
    text = '封条上完整写着：未经许可不得拆封。'
    data['clues'][0]['content'] = text
    data['solution'][0]['evidence'][0]['quote'] = text
    archive = ss.parse_case_to_archive(data, '证据原文')
    archive.validate(require_script=True, require_solution=True)
    assert archive.clues[0].content == text


def test_generated_initial_access_is_narrowed_without_moving_evidence():
    import copy
    data = copy.deepcopy(CASE_DATA)
    data['clues'][1]['holder_id'] = 'char_2'
    data['characters'][0]['clue_ids'] = ['clue_1', 'clue_2', 'unknown']
    data['characters'][1]['clue_ids'] = ['clue_2']
    ss.normalize_generated_clue_refs(data)
    assert data['characters'][0]['clue_ids'] == ['unknown']
    assert data['characters'][1]['clue_ids'] == ['clue_2']
    assert [c['holder_id'] for c in data['clues']] == ['scene', 'char_2', 'scene']
    import pytest
    with pytest.raises(ValueError, match='线索不存在'):
        ss.parse_case_to_archive(data, '错误引用仍需拒绝')


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
        case_data["solution"] = []
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
        monkeypatch.setattr(ss, "load_story", lambda story_id: archive)
        assert len(saves) == 1  # returned before any portrait URL was written
        assert all(not c.portrait_url for c in archive.characters)

        gate.set()  # let the background thread finish
        deadline = time.monotonic() + 5
        while len(saves) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(saves) == 2  # second save persists the updated URLs
        assert all(c.portrait_url for c in saves[1].characters)


def test_generation_retries_invalid_graph_before_accepting(monkeypatch):
    import copy
    import json
    bad = copy.deepcopy(CASE_DATA)
    bad['clues'][0]['required_clue_id'] = 'clue_2'
    bad['clues'][1]['required_clue_id'] = 'clue_1'
    # Both in the same round, so the graph check detects the cycle itself.
    bad['clues'][1]['discovery_round'] = 1
    outputs = iter([json.dumps(bad), json.dumps({"updates": [
        {"path": "/clues/clue_1/required_clue_id", "value": None},
        {"path": "/clues/clue_2/required_clue_id", "value": None},
        {"path": "/clues/clue_2/discovery_round", "value": 2},
    ]})])
    calls = []
    def generate(prompt, *args, **kwargs):
        calls.append(prompt)
        return next(outputs)
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    monkeypatch.setattr(ss, 'review_story_consistency', lambda *args, **kwargs: None)
    result = ss.generate_story('测试', None)
    assert result['clues'][0]['required_clue_id'] is None
    assert result['clues'][1]['discovery_round'] == 2
    assert len(calls) == 2
    assert '循环' in calls[1]
    assert json.dumps(ss.compact_review_data(bad), ensure_ascii=False) in calls[1]
    assert '不要换一个新案件' in calls[1]


def test_semantic_timeline_conflict_retries_and_reviews_again(monkeypatch):
    import json
    outputs = iter([
        json.dumps(CASE_DATA),
        json.dumps({"valid": False, "issues": ["background 写死者九点行动，truth 写八点已死亡"]}),
        json.dumps({"updates": [{"path": "/background", "value": "案件背景"}]}),
        json.dumps({"valid": True, "issues": [], "culprit_id": "char_1", "killer_knowledge_quote": "我是真凶。"}),
    ])
    prompts = []
    def generate(prompt, *args, **kwargs):
        prompts.append(prompt)
        return next(outputs)
    monkeypatch.setattr(ss, "generate_story_text", generate)
    assert ss.generate_story("测试", None) == CASE_DATA
    assert "九点行动" in prompts[2]
    assert len(prompts) == 4


def test_review_confirms_disputed_findings_against_original(monkeypatch):
    import json
    outputs = iter([
        json.dumps({'valid': False, 'issues': ['开场不知死因与后续验尸矛盾']}),
        json.dumps({'valid': True, 'issues': [], 'culprit_id': 'char_1', 'killer_knowledge_quote': '我是真凶。'}),
    ])
    prompts = []
    def generate(prompt, *args, **kwargs):
        prompts.append(prompt)
        return next(outputs)
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    ss.review_story_consistency(CASE_DATA, None)
    assert len(prompts) == 2
    assert json.dumps(ss.compact_review_data(CASE_DATA), ensure_ascii=False) in prompts[1]
    assert '开场不知死因' in prompts[1]


def test_malformed_confirmation_never_accepts_story(monkeypatch):
    import pytest
    outputs = iter(['{"valid":false,"issues":["缺证"]}', '{"valid":"true","issues":[]}'])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *args, **kwargs: next(outputs))
    with pytest.raises(ValueError, match='复核未返回有效结果'):
        ss.review_story_consistency(CASE_DATA, None)


def test_malformed_semantic_review_never_accepts_story(monkeypatch):
    import pytest
    monkeypatch.setattr(ss, "generate_story_text", lambda *args, **kwargs: '{"valid": "true", "issues": []}')
    with pytest.raises(ValueError, match="有效结果"):
        ss.review_story_consistency(CASE_DATA, None)


def test_invalid_generated_story_is_never_saved(monkeypatch):
    _patch_llm(monkeypatch)
    bad = dict(CASE_DATA, true_killer_id='missing')
    monkeypatch.setattr(ss, 'generate_story', lambda *args, **kwargs: bad)
    saves = []
    monkeypatch.setattr(ss, 'save_story', lambda archive: saves.append(archive))
    assert _service_with_key('').create_story('坏剧本') is None
    assert not saves


def test_repairs_structure_then_evidence_with_separate_budgets(monkeypatch):
    import copy
    import json
    bad = copy.deepcopy(CASE_DATA)
    del bad['characters'][1]['objectives']
    bad['clues'][0]['required_clue_id'] = '不存在的前置'
    outputs = iter([
        bad,
        {'updates': [{'path': '/characters/char_2/objectives', 'value': ['调查凶手']}]},
        {'updates': [{'path': '/clues/clue_1/required_clue_id', 'value': None}]},
        {'updates': [{'path': '/clues/clue_1/content', 'value': '物证1；检验已证实毒物。'}]},
    ])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(next(outputs)))
    reviews = []
    def review(data, _, **kw):
        reviews.append(copy.deepcopy(data))
        if '检验' not in data['clues'][0]['content']:
            raise ValueError('定案所需毒物鉴定缺失')
    monkeypatch.setattr(ss, 'review_story_consistency', review)
    result = ss.generate_story('测试', None)
    assert result is not None and len(reviews) == 2
    assert result['characters'] == CASE_DATA['characters']
    assert result['true_killer_id'] == CASE_DATA['true_killer_id']
    assert result['clues'][1:] == CASE_DATA['clues'][1:]


def test_story_patch_is_atomic_and_preserves_identity():
    import copy
    import pytest
    original = copy.deepcopy(CASE_DATA)
    for path in ['/characters', '/characters/char_1/id',  '/clues/clue_1/id',
                 '/characters/2/name', '/clues/-1/content', '/unknown']:
        with pytest.raises(ValueError):
            ss.apply_story_updates(original, {'updates': [
                {'path': '/background', 'value': '不应应用'}, {'path': path, 'value': 'bad'}]})
        assert original == CASE_DATA
    changed = ss.apply_story_updates(original, {'updates': [
        {'path': '/characters/char_2/objectives', 'value': ['新目标']}]})
    assert changed['characters'][1]['objectives'] == ['新目标']
    assert original == CASE_DATA


def test_bad_repairs_are_bounded_and_never_reach_review(monkeypatch):
    import json
    calls, reviews = [], []
    def generate(*a, **kw):
        calls.append(a)
        return json.dumps(dict(CASE_DATA, solution=[]))
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    monkeypatch.setattr(ss, 'review_story_consistency', lambda *a: reviews.append(a))
    assert ss.generate_story('坏修复', None) is None
    assert len(calls) == 3 and reviews == []
    assert '修复提交错误' in calls[2][0]


def test_story_repair_interruption_propagates(monkeypatch):
    import json
    import pytest
    from app.core.errors import ModelInterrupted
    calls = []
    def generate(*a, **kw):
        calls.append(a)
        if len(calls) > 1:
            raise ModelInterrupted('app backgrounded')
        return json.dumps(dict(CASE_DATA, solution=[]))
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    with pytest.raises(ModelInterrupted):
        ss.generate_story('中断', None)
    assert len(calls) == 2


def test_repair_addresses_clues_by_id_not_numeric_suffix():
    import copy
    import pytest
    data = copy.deepcopy(CASE_DATA)
    data['clues'] = list(reversed(data['clues']))
    updated = ss.apply_story_updates(data, {'updates': [
        {'path': '/clues/clue_1/content', 'value': '只修改线索1'}]})
    assert updated['clues'][0] == data['clues'][0]
    assert updated['clues'][2]['content'] == '只修改线索1'
    with pytest.raises(ValueError, match='不存在'):
        ss.apply_story_updates(data, {'updates': [{'path': '/clues/1/content', 'value': '错误下标'}]})


def test_malformed_top_level_field_can_be_repaired_without_crash(monkeypatch):
    import json
    outputs = iter([dict(CASE_DATA, victim=[]), {'updates': [
        {'path': '/victim', 'value': CASE_DATA['victim']}]}])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(next(outputs)))
    monkeypatch.setattr(ss, 'review_story_consistency', lambda *a, **kw: None)
    assert ss.generate_story('字段类型', None) == CASE_DATA


def test_positive_review_cannot_change_culprit_or_invent_personal_admission(monkeypatch):
    import json
    import pytest
    for culprit_id, quote, error in [('char_2', '我在大厅。', '不一致'),
                                     ('char_1', '没有写过的行凶记忆', '作案知识'),
                                     ('char_1', '', '作案知识')]:
        result = dict(valid=True, issues=[], culprit_id=culprit_id, killer_knowledge_quote=quote)
        monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(result))
        with pytest.raises(ValueError, match=error):
            ss.review_story_consistency(CASE_DATA, None, confirm_rejection=False)


def test_new_case_negative_review_requires_repair_not_blanket_confirmation(monkeypatch):
    import json
    import pytest
    calls = []
    def generate(*a, **kw):
        calls.append(a)
        return json.dumps(dict(valid=False, issues=['凶手本人声称未作案']))
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    with pytest.raises(ValueError, match='未作案'):
        ss.review_story_consistency(CASE_DATA, None, confirm_rejection=False)
    assert len(calls) == 1


def test_archive_confirmation_still_needs_correct_culprit(monkeypatch):
    import json
    import pytest
    outputs = iter([dict(valid=False, issues=['真凶错人']),
                    dict(valid=True, issues=[], culprit_id='char_2', killer_knowledge_quote='我在大厅。')])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(next(outputs)))
    with pytest.raises(ValueError, match='不一致'):
        ss.review_story_consistency(CASE_DATA, None)


def test_culprit_metadata_correction_requires_new_review(monkeypatch):
    import copy
    import json
    import pytest
    wrong = copy.deepcopy(CASE_DATA)
    wrong['true_killer_id'] = 'char_2'
    outputs = iter([wrong, {'updates': [{'path': '/true_killer_id', 'value': 'char_1'}]}])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(next(outputs)))
    reviewed = []
    def review(data, _, **kw):
        reviewed.append(data['true_killer_id'])
        if data['true_killer_id'] != 'char_1':
            raise ValueError('实际致死者与真凶ID不一致')
    monkeypatch.setattr(ss, 'review_story_consistency', review)
    assert ss.generate_story('ID误填', None)['true_killer_id'] == 'char_1'
    assert reviewed == ['char_2', 'char_1']
    assert wrong['true_killer_id'] == 'char_2'
    with pytest.raises(ValueError, match='已有角色'):
        ss.apply_story_updates(wrong, {'updates': [{'path': '/true_killer_id', 'value': 'unknown'}]})


def test_story_quality_mode_is_bounded_and_provider_specific(monkeypatch):
    from types import SimpleNamespace
    requests, options = [], []
    class Client:
        def __init__(self): self.chat = self.completions = self
        def with_options(self, **kwargs): options.append(kwargs); return self
        def create(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))])
    monkeypatch.setattr(ss, 'trace_llm_chat', lambda **kw: None)
    config = SimpleNamespace(base_url='https://api.deepseek.com/v1', model_name='deepseek-v4-pro')
    monkeypatch.setattr(ss, 'get_config', lambda: SimpleNamespace(deepseek=config))
    assert ss.generate_story_text('虚构测试', Client()) == '{}'
    assert requests[-1]['extra_body'] == {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'}
    assert requests[-1]['response_format'] == {'type': 'json_object'}
    assert options == [{'timeout': 300, 'max_retries': 0}]
    config.base_url = 'https://example.invalid/v1'
    ss.generate_story_text('虚构测试', Client())
    assert requests[-1]['extra_body'] == {'thinking': {'type': 'disabled'}}
    assert 'response_format' not in requests[-1]
    assert len(options) == 1


def test_noop_repair_uses_distinct_attempt_prompt_for_mobile_cache(monkeypatch):
    import json
    prompts = []
    def generate(prompt, *a, **kw):
        prompts.append(prompt)
        return json.dumps(dict(CASE_DATA, solution=[])) if len(prompts) == 1 else json.dumps(
            {'updates': [{'path': '/solution', 'value': []}]})
    monkeypatch.setattr(ss, 'generate_story_text', generate)
    assert ss.generate_story('不能复用失败修补', None) is None
    assert len(prompts) == 3
    assert '"repair_attempt": 1' in prompts[1] and '"repair_attempt": 2' in prompts[2]


def test_quote_copying_errors_use_same_real_clue_and_still_need_semantic_review(monkeypatch):
    import copy
    import json
    data = copy.deepcopy(CASE_DATA)
    data['solution'][0]['evidence'][0]['quote'] = '同义改写但不是原文'
    data['solution'][0]['evidence'].append({'clue_id': 'missing', 'quote': '不要推断ID'})
    ss.normalize_generated_evidence_quotes(data)
    assert data['solution'][0]['evidence'] == [
        {'clue_id': 'clue_1', 'quote': '物证1'}, {'clue_id': 'missing', 'quote': '不要推断ID'}]
    data['solution'][0]['evidence'].pop()
    data['solution'][0]['conclusion'] = '物证1并不能证明的行凶者'
    calls = []
    def review(draft, client, **kw):
        calls.append(draft)
        raise ValueError('引用真实原文不代表支持结论')
    monkeypatch.setattr(ss, 'review_story_consistency', review)
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: json.dumps(data))
    assert ss.generate_story('仍然缺证', None) is None
    assert len(calls) == 1


def test_compact_review_keeps_all_facts_partial_quotes_and_original_archive():
    import copy
    data = copy.deepcopy(CASE_DATA)
    data['solution'][0]['evidence'].append({'clue_id': 'clue_2', 'quote': '物'})
    before = copy.deepcopy(data)
    compact = ss.compact_review_data(data)
    assert data == before
    assert compact['clues'] == data['clues']
    assert compact['characters'] == data['characters']
    assert compact['truth'] == data['truth']
    assert compact['solution'][0]['evidence'] == [
        {'clue_id': 'clue_1', 'quote': ''}, {'clue_id': 'clue_2', 'quote': '物'}]


def test_semantic_review_keeps_thinking_and_repairs_are_reviewed_separately(monkeypatch):
    from types import SimpleNamespace
    requests = []
    class Client:
        def __init__(self): self.chat = self.completions = self
        def with_options(self, **kwargs): return self
        def create(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))])
    monkeypatch.setattr(ss, 'trace_llm_chat', lambda **kw: None)
    monkeypatch.setattr(ss, 'get_config', lambda: SimpleNamespace(deepseek=SimpleNamespace(
        base_url='https://api.deepseek.com/v1', model_name='deepseek-v4-pro')))
    for purpose, limit in [('review', 12 * 1024), ('repair', 8192)]:
        ss.generate_story_text('测试JSON', Client(), purpose=purpose)
        expected = {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'} if purpose == 'review' else {'thinking': {'type': 'disabled'}}
        assert requests[-1]['extra_body'] == expected
        assert requests[-1]['response_format'] == {'type': 'json_object'}
        assert requests[-1]['max_tokens'] == limit


def test_progress_reports_real_repair_and_revalidation(monkeypatch):
    import json
    stages, reviews = [], []
    monkeypatch.setattr(ss, 'report_story_progress', lambda stage, label: stages.append(stage))
    def review(data, client, **kw):
        reviews.append(data['truth'])
        if len(reviews) == 1:
            raise ValueError('电话方向矛盾')
    outputs = iter([json.dumps(CASE_DATA), json.dumps({'updates': [{'path': '/truth', 'value': '修订真相'}]})])
    monkeypatch.setattr(ss, 'generate_story_text', lambda *a, **kw: next(outputs))
    monkeypatch.setattr(ss, 'review_story_consistency', review)
    assert ss.generate_story('进度测试', None)['truth'] == '修订真相'
    assert stages == ['draft', 'structure', 'review', 'repair', 'structure', 'review']
    assert reviews == ['真相叙述', '修订真相']
