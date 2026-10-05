"""Run against staged APK source with python -S: no SDK, dotenv or web server."""
import asyncio
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

from app.core.errors import GameError, ModelInterrupted
from mobile_model import NativeModelClient, operation
from mobile_runtime import Runtime
from mobile_store import MobileStore

BUNDLED = Path(__file__).resolve().parents[2] / 'frontend/android/app/build/generated/game-assets/stories'


class Transport:
    def __init__(self):
        self.calls = []
        self.fail_statement = False
        self.fail_vote = False
        self.active = True
        self.lock = threading.Lock()

    def settings(self):
        return json.dumps(dict(baseUrl='https://example.invalid/v1', storyModel='story',
                               roleModel='role', reviewModel='review', thinking=False))

    def isActive(self):
        return self.active

    def complete(self, encoded, timeout, base):
        payload = json.loads(encoded)
        function = payload.get('tool_choice', {}).get('function', {}).get('name')
        with self.lock:
            self.calls.append(payload)
            if function == 'submit_statement' and self.fail_statement:
                self.fail_statement = False
                return json.dumps({'error': '模拟断网'})
            if function == 'submit_vote' and self.fail_vote:
                self.fail_vote = False
                return json.dumps({'error': '模拟表决断网'})
        if function == 'submit_statement':
            data = {'segments': [{'text': '我还不能确定。', 'kind': 'aside', 'source_ids': []}], 'corrections': []}
        elif function == 'check_statement':
            request = json.loads(payload['messages'][1]['content'])
            data = {'valid': True, 'issues': [], 'segments': [
                {'segment_index': i, 'supported': True, 'non_factual': True,
                 'source_id': '', 'quote': '', 'unsupported_details': []}
                for i in range(len(request['speech_segments']))]}
        elif function == 'submit_vote':
            context = json.loads(payload['messages'][1]['content'])
            data = {'target_id': context['candidates'][0], 'brief_reason': ''}
        else:
            if len(payload.get('messages', [])) < 2:
                return json.dumps({'choices': [{'message': {'content': 'cache probe'}}]})
            case = json.loads(payload['messages'][1]['content'].rsplit('\n', 1)[-1])
            culprit_id = case.get('true_killer_id') or case['case']['true_killer']
            culprit = next(c for c in case['characters'] if c['id'] == culprit_id)
            review = dict(valid=True, issues=[], culprit_id=culprit_id, killer_knowledge_quote=culprit['self_knowledge'])
            return json.dumps({'choices': [{'message': {'content': json.dumps(review)}}]})
        # Deliberately omit content, as some compatible providers do for tool calls.
        return json.dumps({'choices': [{'message': {'tool_calls': [{'type': 'function',
            'function': {'name': function, 'arguments': json.dumps(data, ensure_ascii=False)}}]}}],
            'usage': {'prompt_tokens': 100, 'prompt_cache_hit_tokens': 20}})


class MobileRuntimeTests(unittest.TestCase):
    def test_downloaded_content_adds_dynamic_cast_without_model_or_game_revision_change(self):
        from app.services import story_content_service as content
        from app.core.content_protocol import content_fingerprint, artwork_files
        async def check():
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary) / 'game'
                directory.mkdir()
                transport = Transport()
                runtime = Runtime(str(directory), BUNDLED, transport)
                revision = runtime.revision
                source = Path(__file__).resolve().parents[2] / 'backend/app/content/stories'
                for suffix in ['3304', '3305', '3306']:
                    sid = 'ad60c7e0-1f56-4fc3-bcaa-705910d0' + suffix
                    raw = (source / f'{sid}.json').read_bytes()
                    package = json.loads(raw)
                    version = package['metadata']['version']
                    images = {name: (source.parent / 'images' / sid / name).read_bytes()
                              for name in artwork_files(package)}
                    import hashlib
                    digest = hashlib.sha256(raw).hexdigest()
                    pack = Path(temporary) / 'story-library/packs' / sid / f'v{version}-{digest}'
                    pack.mkdir(parents=True)
                    (pack / 'package.json').write_bytes(raw)
                    if images:
                        (pack / 'images').mkdir()
                        for name, data in images.items():
                            (pack / 'images' / name).write_bytes(data)
                    (pack / 'complete.json').write_text(json.dumps({'story_id': sid, 'version': version, 'sha256': digest,
                        'fingerprint': content_fingerprint(raw, images), 'min_engine_version': 1}))
                    content.activate(sid, version, digest, str(directory / 'stories'))
                self.assertEqual(runtime.revision, revision)
                books = runtime.read('/stories')['stories']
                self.assertEqual([book['num_characters'] for book in books if book['origin'] == 'builtin'], [3, 5, 7, 4, 6, 8])
                for book in books:
                    if book.get('delivery') != 'downloaded':
                        continue
                    task = await runtime.command({'kind': 'start', 'id': str(uuid.uuid4()),
                        'endpoint': '/games/load', 'body': {'story_id': book['id'], 'mode': 'quick'}})
                    for _ in range(500):
                        result = runtime.store.get('tasks', task['id'])
                        if result['state'] not in ('queued', 'running'):
                            break
                        await asyncio.sleep(.005)
                    self.assertEqual(result['state'], 'done', result.get('error'))
                    session = runtime.manager.get(result['game_id'])
                    self.assertEqual(len(session.ai_characters), book['num_characters'] - 1)
                self.assertEqual(transport.calls, [])
                restarted = Runtime(str(directory), BUNDLED, transport)
                self.assertEqual(len(restarted.manager.list_active()), 3)
                self.assertTrue(all(s.archive.catalog['content_ref']['delivery'] == 'downloaded'
                                    for s in restarted.manager._sessions.values()))
        asyncio.run(check())

    def test_legacy_backup_freezes_pre_upgrade_body_and_keeps_private_memories(self):
        import shutil
        async def check():
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary) / 'game'; directory.mkdir()
                bundle = Path(temporary) / 'bundled'
                shutil.copytree(BUNDLED, bundle)
                transport = Transport()
                runtime = Runtime(str(directory), bundle, transport)
                archive = runtime.stories.get_playable_story(runtime.read('/stories')['stories'][0]['id'])
                gid, game = runtime.manager.create_session(archive=archive)
                snapshot = game.to_snapshot(gid)
                snapshot.pop('archive'); snapshot['schema_version'] = 1
                npc = next(iter(game.ai_characters))
                snapshot['ai_memories'] = {npc: [{'role': 'assistant', 'message': '旧版私密证言'}]}
                runtime.store.save(snapshot)
                old = json.loads((bundle / 'catalog' / f'{archive.id}.json').read_text())
                old['archive']['title'] = '更新前的冻结正文'
                old['metadata']['version'] = 1
                legacy = bundle / 'legacy-catalog'; legacy.mkdir()
                (legacy / f'{archive.id}.json').write_text(json.dumps(old))
                runtime = Runtime(str(directory), bundle, transport)
                restored = runtime.manager.get(gid)
                self.assertEqual(restored.archive.title, '更新前的冻结正文')
                self.assertEqual(restored.archive.catalog['version'], 1)
                self.assertTrue(any(event.text == '旧版私密证言' and event.kind == 'legacy_memory'
                                    for event in restored.game.state.discussion_events))
                self.assertEqual(runtime.store.get('sessions', gid)['archive']['title'], '更新前的冻结正文')
                self.assertEqual(transport.calls, [])
        asyncio.run(check())

    def test_story_progress_is_durable_and_does_not_expose_private_task_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime.__new__(Runtime)
            runtime.store = MobileStore(directory)
            task = {'id': 'progress-test', 'state': 'running', 'endpoint': '/games',
                    'settings': {'private': 'settings'}, 'body': {'private': 'topic'}}
            token = operation.set(task)
            try:
                runtime.story_progress('repair', '正在修补证据矛盾')
            finally:
                operation.reset(token)
            view = runtime.task_view(runtime.store.get('tasks', task['id']))
            self.assertEqual(view['progress'], {'stage': 'repair', 'label': '正在修补证据矛盾'})
            self.assertNotIn('settings', view)
            self.assertNotIn('body', view)
            runtime.story_progress('save', '不应写入其他任务')
            self.assertEqual(runtime.store.get('tasks', task['id'])['progress']['stage'], 'repair')

    def test_cached_response_and_explicit_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            transport, store = Transport(), MobileStore(directory)
            client = NativeModelClient(transport, store)
            task = {'id': 'cache-test', 'attempt': 1, 'settings': json.loads(transport.settings())}
            token = operation.set(task)
            try:
                arguments = dict(model='m', messages=[{'role': 'user', 'content': 'test'}])
                client.create(**arguments)
                transport.active = False
                replay = client.create(**arguments)
                self.assertIsNotNone(replay.choices[0].message.content)
                self.assertTrue(replay.usage['local_reused'])
                self.assertEqual(len(transport.calls), 1)
                with self.assertRaises(ModelInterrupted):
                    client.create(**{**arguments, 'model': 'new'})
                transport.active = True
                transport.fail_statement = True
                request = dict(model='m', tool_choice={'function': {'name': 'submit_statement'}})
                with self.assertRaises(ModelInterrupted):
                    client.create(**request)
                with self.assertRaises(ModelInterrupted):
                    client.create(**request)
                self.assertEqual(len(transport.calls), 2)
                task['attempt'] += 1
                self.assertIsNone(client.create(**request).choices[0].message.content)
                self.assertEqual(len(transport.calls), 3)
            finally:
                operation.reset(token)

    def test_full_quick_game_with_restart_and_interrupted_discussion(self):
        async def play():
            with tempfile.TemporaryDirectory() as directory:
                transport = Transport()
                runtime = Runtime(directory, BUNDLED, transport)

                async def wait(task):
                    for _ in range(1000):
                        saved = runtime.store.get('tasks', task['id'])
                        if saved['state'] not in ('queued', 'running'):
                            return saved
                        await asyncio.sleep(.005)
                    self.fail('task did not finish')

                async def start(endpoint, body=None, key=None):
                    task = await runtime.command({'kind': 'start', 'id': key or str(uuid.uuid4()),
                                                  'endpoint': endpoint, 'body': body or {}})
                    return await wait(task)

                stories = runtime.read('/stories')['stories']
                loaded = await start('/games/load', {'story_id': stories[0]['id'], 'mode': 'quick'})
                self.assertEqual(loaded['state'], 'done', loaded.get('error'))
                self.assertEqual(len(transport.calls), 0)
                gid = loaded['result']['game_id']
                prefix = f'/games/{gid}'
                count = len(transport.calls)
                repeated = await start('/games/load', loaded['body'], loaded['id'])
                self.assertEqual(repeated['result']['game_id'], gid)
                self.assertEqual(len(transport.calls), count)
                with self.assertRaises(GameError):
                    await start('/games/load', {'story_id': 'different'}, loaded['id'])
                before_intro_calls = len(transport.calls)
                intro = await start(prefix+'/introduce')
                self.assertEqual(intro['state'], 'done')
                self.assertEqual(len(transport.calls), before_intro_calls)
                runtime = Runtime(directory, BUNDLED, transport)
                self.assertEqual((await start(prefix+'/introduce', {}, intro['id']))['state'], 'done')
                self.assertEqual(len(runtime.read(prefix+'/discussion-history')['history']),
                                 len(runtime.manager.get(gid).archive.characters))
                self.assertEqual((await start(prefix+'/next-phase'))['state'], 'done')

                for round_number in range(1, 4):
                    status = runtime.read(prefix)
                    self.assertEqual(status['round'], round_number)
                    options = status['investigation_options']
                    if options:
                        self.assertEqual((await start(prefix+'/investigate', {'lead_id': options[0]['id']}))['state'], 'done')
                    self.assertEqual((await start(prefix+'/next-phase'))['state'], 'done')
                    if round_number == 1:
                        transport.fail_statement = True
                    task = await start(prefix+'/speak', {'message': '请说明你知道的情况。'})
                    if round_number == 1:
                        self.assertEqual(task['state'], 'interrupted', task.get('error'))
                        session = runtime.manager.get(gid)
                        pending = session.pending_discussion
                        self.assertGreater(len(pending['completed']), 0)
                        completed = len(pending['completed'])
                        frozen = json.dumps(pending['contexts'], sort_keys=True)
                        before = len(session.game.state.discussion_events)
                        with self.assertRaises(GameError):
                            await start(prefix+'/speak', {'message': '不能偷偷替换原问题'})
                        # Reconstruct exactly as a fresh process does; the task is manually continued.
                        task.pop('game_id', None)
                        runtime.store.put('tasks', task['id'], task)
                        runtime = Runtime(directory, BUNDLED, transport)
                        session = runtime.manager.get(gid)
                        view = runtime.task_view(runtime.store.get('tasks', task['id']))
                        self.assertEqual(view['game_id'], gid)
                        self.assertEqual(view['title'], session.archive.title)
                        self.assertTrue(view['can_continue'])
                        self.assertEqual(json.dumps(session.pending_discussion['contexts'], sort_keys=True), frozen)
                        await runtime.command({'kind': 'continue', 'id': task['id']})
                        task = await wait(task)
                        self.assertEqual(task['state'], 'done', task.get('error'))
                        self.assertEqual(len(session.game.state.discussion_events) - before,
                                         len(session.ai_characters) - completed)
                        self.assertIsNone(session.pending_discussion)
                        # Simulate death after saving the round, before the terminal task record.
                        task['state'] = 'running'; runtime.store.put('tasks', task['id'], task)
                        runtime = Runtime(directory, BUNDLED, transport)
                        before_calls = len(transport.calls)
                        before_history = runtime.read(prefix+'/discussion-history')
                        await runtime.command({'kind': 'continue', 'id': task['id']})
                        self.assertEqual((await wait(task))['state'], 'done')
                        self.assertEqual(runtime.read(prefix+'/discussion-history'), before_history)
                        self.assertEqual(len(transport.calls), before_calls)
                    else:
                        self.assertEqual(task['state'], 'done', task.get('error'))
                    if round_number < 3:
                        self.assertEqual((await start(prefix+'/next-investigation-round'))['state'], 'done')
                self.assertEqual((await start(prefix+'/start-voting'))['state'], 'done')
                session = runtime.manager.get(gid)
                target = session.game.get_character(session.game.killer_id).name
                before_calls = len(transport.calls)
                result = await start(prefix+'/vote', {'character_name': target})
                self.assertEqual(result['state'], 'done')
                self.assertEqual(len(transport.calls), before_calls)
                # Death after the terminal snapshot, before publishing task completion.
                result['state'] = 'running'; runtime.store.put('tasks', result['id'], result)
                runtime = Runtime(directory, BUNDLED, transport)
                await runtime.command({'kind': 'continue', 'id': result['id']})
                result = await wait(result)
                self.assertEqual(result['state'], 'done', result.get('error'))
                self.assertEqual(len(transport.calls), before_calls)
                transport.fail_vote = True
                advice = await start(prefix+'/ballot-advice')
                self.assertEqual(advice['state'], 'interrupted')
                frozen_ballots = json.dumps(runtime.manager.get(gid).pending_ballots['contexts'], sort_keys=True)
                before_calls = len(transport.calls)
                runtime = Runtime(directory, BUNDLED, transport)
                self.assertEqual(json.dumps(runtime.manager.get(gid).pending_ballots['contexts'], sort_keys=True), frozen_ballots)
                await runtime.command({'kind': 'continue', 'id': advice['id']})
                advice = await wait(advice)
                self.assertEqual(advice['state'], 'done', advice.get('error'))
                self.assertEqual(len(transport.calls) - before_calls, 1)
                self.assertEqual(advice['result']['winner'], 'good')
                self.assertTrue(result['result']['game_ended'])
                runtime = Runtime(directory, BUNDLED, transport)
                self.assertEqual(runtime.read(prefix)['phase'], 'reveal')
                self.assertEqual(runtime.read(prefix+'/reveal')['case_info']['true_killer_name'], target)
                with self.assertRaises(GameError):
                    runtime.read(prefix+'/unknown')
                self.assertFalse(any(module in __import__('sys').modules for module in ('fastapi', 'openai', 'dotenv')))
        asyncio.run(play())

class CatalogMobileTests(unittest.TestCase):
    def test_catalog_import_updates_only_new_games_and_invalid_counts_stay_offline(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                transport = Transport()
                runtime = Runtime(directory, BUNDLED, transport)
                items = runtime.read('/stories')['stories']
                self.assertEqual([s['num_characters'] for s in items if s['origin'] == 'builtin'], [3, 5, 7])
                async def perform(endpoint, body):
                    task = await runtime.command({'kind': 'start', 'id': str(uuid.uuid4()), 'endpoint': endpoint, 'body': body})
                    for _ in range(400):
                        result = runtime.store.get('tasks', task['id'])
                        if result['state'] not in ('queued', 'running'):
                            return result
                        await asyncio.sleep(.005)
                    self.fail('local task did not finish')
                for item in items:
                    if item['origin'] != 'builtin':
                        continue
                    opened = await perform('/games/load', {'story_id': item['id'], 'mode': 'quick'})
                    self.assertEqual(opened['state'], 'done', opened.get('error'))
                    game_id = opened['result']['game_id']
                    session = runtime.manager.get(game_id)
                    self.assertEqual(session.archive.id, item['id'])
                    self.assertEqual(len(session.ai_characters), item['num_characters'] - 1)
                    self.assertEqual(runtime.read('/games/' + game_id)['phase'], 'introduction')
                self.assertEqual(len(transport.calls), 0)
                package = json.loads(next((BUNDLED / 'catalog').glob('ad*.json')).read_text())
                package['archive']['id'] = str(uuid.uuid4())
                package['metadata']['version'] = 1
                first = await perform('/stories/import', {'package': package})
                self.assertEqual(first['state'], 'done')
                retry = await perform('/stories/import', {'package': package})
                self.assertEqual(retry['state'], 'done')
                loaded = await perform('/games/load', {'story_id': package['archive']['id']})
                gid = loaded['result']['game_id']
                package['metadata']['version'] = 2
                package['archive']['title'] = '移动端修订版'
                self.assertEqual((await perform('/stories/import', {'package': package}))['state'], 'done')
                runtime = Runtime(directory, BUNDLED, transport)
                self.assertEqual(runtime.manager.get(gid).archive.catalog['version'], 1)
                self.assertEqual(runtime.stories.get_story(package['archive']['id']).catalog['version'], 2)
                invalid = await perform('/games', {'topic': '不该请求模型', 'character_count': 9})
                self.assertEqual(invalid['state'], 'failed')
                self.assertEqual(invalid['status'], 422)
                self.assertEqual(len(transport.calls), 0)
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
