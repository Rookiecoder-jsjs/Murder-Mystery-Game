"""Application-owned native runtime; no HTTP server and no external Python install."""
import asyncio
import hashlib
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from app.core.config import AppConfig, DeepSeekConfig, RoleplayConfig, QwenImageConfig, configure_app, get_config
from app.core.errors import GameError, ModelInterrupted
from app.core.runtime import configure_embedded
from mobile_store import MobileStore
from mobile_model import NativeModelClient, operation

_runtime = None
_loop = None


class Runtime:
    def __init__(self, directory: str, bundled: str | Path, transport) -> None:
        self.store = MobileStore(directory)
        self.transport = transport
        self.active = None
        self.revision = 0
        configure_embedded(directory, lambda _kind: NativeModelClient(transport, self.store),
                           self.story_progress)
        from app.services import story_catalog
        if (Path(bundled) / 'catalog' / 'manifest.json').exists():
            story_catalog.CONTENT_DIR = Path(bundled) / 'catalog'
        from app.services import story_content_service
        story_content_service.configure(Path(directory).parent / 'story-library')
        from app.services import story_service
        from app.services.story_service import StoryService
        from app.services.session_service import SessionManager
        stories = Path(directory) / 'stories'
        stories.mkdir(exist_ok=True)
        story_service.STORIES_DIR = str(stories)
        for source in Path(bundled).glob('*.json'):
            destination = stories / source.name
            if not destination.exists():
                shutil.copyfile(source, destination)
        self.configure(json.loads(str(transport.settings())))
        self.stories = StoryService()
        # EngineHost keeps the pre-upgrade catalog before replacing APK files.
        # Freeze only legacy snapshots; complete snapshots are already isolated.
        for snapshot in self.store.load_all():
            if 'archive' in snapshot:
                continue
            story_id = snapshot.get('story_id', '')
            if not isinstance(story_id, str) or not story_id:
                continue
            try:
                if str(uuid.UUID(story_id)) != story_id:
                    continue
                old = Path(bundled) / 'legacy-catalog' / f'{story_id}.json'
                if old.exists():
                    package = json.loads(old.read_text())
                    archive = story_catalog.parse_package(package, 'builtin')
                    story_catalog._apply_builtin_artwork(archive, package.get('artwork', {}))
                    snapshot['archive'] = archive.to_dict()
                    # Preserve the old schema until from_snapshot migrates its
                    # private memories; to_snapshot writes schema 4 afterwards.
                    self.store.save(snapshot)
            except (ValueError, OSError, KeyError):
                pass  # Preserve the existing legacy fallback; never discard saves.
        self.manager = SessionManager(NativeModelClient(transport, self.store), self.stories, self.store)
        self.manager.load_all_persisted()
        for task in self.store.all('tasks'):
            if task['state'] in ('queued', 'running'):
                task.update(state='interrupted', error='应用上次运行被中断；已完成的记录已保存')
                self.store.put('tasks', task['id'], task)

    def configure(self, settings: dict) -> None:
        configure_app(AppConfig(
            deepseek=DeepSeekConfig('', settings['baseUrl'], settings['storyModel']),
            roleplay=RoleplayConfig('', settings['baseUrl'], settings['roleModel'],
                                   review_model_name=settings['reviewModel']),
            qwen_image=QwenImageConfig(''),
        ))

    def task_view(self, task: dict) -> dict:
        view = {k: task[k] for k in ('id', 'state', 'error', 'status', 'result', 'endpoint', 'created', 'progress', 'game_id') if k in task}
        parts = task['endpoint'].strip('/').split('/')
        # A process can stop after queuing an existing-game action but before
        # execute() persists game_id. Recover only the ID already in its route.
        game_id = task.get('game_id') or (parts[1] if len(parts) >= 3 and parts[0] == 'games' else None)
        if game_id:
            view['game_id'] = game_id
        action = task['endpoint'].rsplit('/', 1)[-1]
        view['label'] = {'games': '生成新案件', 'load': '新开一局', 'introduce': '开场介绍',
            'speak': '本次询问', 'stream': '本次询问', 'vote': '保存最终判断', 'ballot-advice': '人物判断',
            'investigate': '调查证据', 'next-investigation-round': '下一轮调查',
            'import': '安装剧本包', 'return-to-investigation': '补充调查', 'start-voting': '进入表决', 'next-phase': '推进阶段'}.get(action, '游戏操作')
        manager = getattr(self, 'manager', None)
        session = manager._sessions.get(game_id) if manager else None
        if session:
            view['title'] = session.archive.title
        view['can_continue'] = task['state'] == 'interrupted' or bool(session and session.pending_discussion
            and session.pending_discussion['action_id'] == task['id'])
        return view

    def story_progress(self, stage: str, label: str) -> None:
        # asyncio.to_thread carries operation into the story worker. Only the
        # active task is updated, and the public view never includes settings.
        task = operation.get()
        if task is not None:
            task['progress'] = {'stage': stage, 'label': label}
            self.store.put('tasks', task['id'], task)

    async def command(self, command: dict) -> dict:
        """Serialize commands and acknowledge mutations after recording their task IDs."""
        kind = command.get('kind')
        if kind == 'task':
            task = self.store.get('tasks', command['id'])
            if not task:
                raise GameError(404, '任务不存在')
            return self.task_view(task)
        if kind == 'tasks':
            return {'tasks': [self.task_view(t) for t in self.store.all('tasks')
                              if t['state'] not in ('done', 'dismissed')]}
        if kind == 'dismiss':
            task = self.store.get('tasks', command['id'])
            if not task or task['state'] != 'failed':
                raise GameError(409, '正在进行或尚待恢复的任务不能移除')
            if any(s.pending_discussion and s.pending_discussion['action_id'] == task['id']
                   for s in self.manager._sessions.values()):
                raise GameError(409, '本局讨论尚未完成，请继续原任务')
            task['state'] = 'dismissed'
            self.store.put('tasks', task['id'], task)
            return {}
        if kind == 'games':
            return {'games': [{'game_id': gid, 'title': session.archive.title,
                               'phase': session.game.state.phase, 'round': session.game.state.round,
                               'player': session._char_name(session.human_player_id),
                               'last_activity': session.last_activity}
                              for gid, session in self.manager._sessions.items()]}
        if kind == 'read':
            return self.read(command['endpoint'])
        if kind == 'start':
            key = str(uuid.UUID(command['id']))
            body = command.get('body', {})
            if not isinstance(body, dict):
                raise GameError(400, '操作参数无效')
            request = {'endpoint': command['endpoint'], 'body': body}
            digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            task = self.store.get('tasks', key)
            if task and task['digest'] != digest:
                raise GameError(409, '同一操作标识的内容发生变化')
            if task:
                return self.task_view(task)
            if self.active:
                raise GameError(409, '上一项操作仍在执行')
            game_prefix = '/'.join(command['endpoint'].split('/')[:3]) + '/'
            if game_prefix.startswith('/games/') and any(
                (old['state'] == 'interrupted' or (old['state'] == 'failed' and self.task_view(old)['can_continue']))
                and old['endpoint'].startswith(game_prefix)
                for old in self.store.all('tasks')
            ):
                raise GameError(409, '本局有未完成操作，请继续原任务')
            task = dict(id=key, digest=digest, **request, state='queued', created=time.time(), attempt=0,
                        settings=json.loads(str(self.transport.settings())))
        elif kind == 'continue':
            task = self.store.get('tasks', command['id'])
            if not task or task['state'] not in ('interrupted', 'failed'):
                raise GameError(409, '任务不可继续')
            if self.active:
                raise GameError(409, '上一项操作仍在执行')
            # An explicit retry may use corrected model names or a new service.
            # Keep the original request, saved replies and frozen role contexts.
            task.setdefault('legacy_cache_base_url', task['settings']['baseUrl'])
            task['settings'] = json.loads(str(self.transport.settings()))
        else:
            raise GameError(400, '未知引擎命令')
        task.update(state='queued', error='', attempt=task['attempt'] + 1)
        self.store.put('tasks', task['id'], task)
        self.active = task['id']
        asyncio.create_task(self.execute(task))
        return self.task_view(task)

    def read(self, endpoint: str) -> dict:
        if endpoint == '/stories':
            return {'stories': self.stories.get_all_stories()}
        parts = endpoint.strip('/').split('/')
        if len(parts) not in (2, 3) or parts[0] != 'games':
            raise GameError(404, '未知游戏查询')
        session = self.manager.get(parts[1])
        action = parts[2] if len(parts) == 3 else ''
        reads = {'': session.get_game_status, 'clues': session.get_clue_board,
                 'reveal': session.get_reveal_info,
                 'discussion-history': lambda: {'history': session.get_discussion_history()},
                 'snapshot': lambda: {'status': session.get_game_status(), 'clues': session.get_clue_board(),
                                     'history': session.get_discussion_history(), 'revision': self.revision}}
        if action not in reads:
            raise GameError(404, '未知游戏查询')
        result = reads[action]()
        if action == '':
            result['is_speaking'] = result['is_speaking'] or bool(self.active)
        return result

    async def execute(self, task: dict) -> None:
        """Commit terminal task status together with all changed game snapshots."""
        token = operation.set(task)
        try:
            self.configure(task['settings'])
            task['state'] = 'running'
            self.store.put('tasks', task['id'], task)
            task['result'] = await self.mutate(task)
            if task.get('game_id') in self.manager.list_active():
                self.manager.get(task['game_id']).last_activity = time.time()
            task.update(state='done', error='')
        except ModelInterrupted as error:
            task.update(state='interrupted', error=str(error))
        except GameError as error:
            task.update(state='failed', error=error.detail, status=error.status_code)
        except ValueError:
            task.update(state='failed', status=422,
                        error='剧本内容未通过一致性校验，请选择其他剧本或生成新案件')
        except Exception:
            task.update(state='failed', error='操作未完成，请检查模型设置或稍后继续')
        finally:
            try:
                self.store.commit_task(task, [s.to_snapshot(gid) for gid, s in self.manager._sessions.items()])
                self.revision += 1
            finally:
                self.active = None
                operation.reset(token)

    async def mutate(self, task: dict) -> dict:
        endpoint, body = task['endpoint'], task['body']
        if endpoint == '/stories/import':
            try:
                return {'story': await asyncio.to_thread(self.stories.import_package, body.get('package'))}
            except ValueError as error:
                raise GameError(422, str(error)) from error
        if endpoint in ('/games', '/games/load'):
            # A completed creation remains discoverable even if UI response was lost.
            if task['id'] in self.manager.list_active():
                session = self.manager.get(task['id'])
                return session.get_game_status()
            if endpoint == '/games/load':
                archive = await asyncio.to_thread(self.stories.get_playable_story, body.get('story_id', ''))
                if archive is None:
                    raise GameError(404, '剧本不存在或存档已损坏')
                gid, session = self.manager.create_session(archive=archive, mode=body.get('mode', 'quick'), game_id=task['id'])
            else:
                from app.services.story_catalog import validate_character_count
                try:
                    validate_character_count(body.get('character_count'))
                except ValueError as error:
                    raise GameError(422, str(error)) from error
                topic = str(body.get('topic', '')).strip()
                if not topic or len(topic) > 2000:
                    raise GameError(400, '请输入有效的案件主题')
                archive = await asyncio.to_thread(self.stories.create_story, topic, character_count=body.get('character_count'))
                if archive is None:
                    raise GameError(422, '剧本生成或一致性审查未通过')
                gid, session = self.manager.create_session(archive=archive, mode=body.get('mode', 'quick'), game_id=task['id'])
            task['game_id'] = gid
            self.store.commit_task(task, [session.to_snapshot(gid)])
            return session.get_game_status()
        parts = endpoint.strip('/').split('/')
        if len(parts) < 3 or parts[0] != 'games':
            raise GameError(404, '未知游戏动作')
        session = self.manager.get(parts[1])
        task['game_id'] = parts[1]
        session.roleplay_config = get_config().roleplay
        for ai in session.ai_characters.values():
            ai.config = session.roleplay_config
        action = '/'.join(parts[2:])
        if action == 'introduce':
            return await session.player_introduce_async(body.get('message', ''))
        if action == 'investigate':
            return session.investigate(body.get('lead_id'))
        if action in ('speak', 'speak/stream'):
            if session.pending_discussion:
                if session.pending_discussion['action_id'] != task['id']:
                    raise GameError(409, '请继续原来的讨论任务')
                messages = [msg async for msg in session.resume_speak_async()]
            elif any(e.action_id == task['id'] for e in session.game.state.discussion_events):
                # A process can stop between saving the completed round and its task result.
                messages = [{'speaker': session._char_name(e.speaker_id), 'message': e.text}
                            for e in session.game.state.discussion_events
                            if e.action_id == task['id'] and e.kind != 'question']
            else:
                messages = await session.player_speak_collect(body['message'], body.get('target_id'), body.get('presented_clue_ids'), task['id'])
            return {'messages': messages, 'phase': session.game.state.phase}
        phases = {'next-phase': session.advance_phase, 'return-to-investigation': session.return_to_investigation,
                  'start-voting': session.start_voting, 'next-investigation-round': session.start_next_round}
        if action in phases:
            return phases[action]()
        if action == 'ballot-advice':
            return await session.collect_ballot_advice()
        if action in ('vote', 'accuse'):
            result = (await session.vote_async(body['character_name'], task['id'])) if action == 'vote' else session.accuse(body['character_name'])
            if result['game_ended']:
                result['reveal'] = session.get_reveal_info()
            return result
        raise GameError(404, '未知游戏动作')


def initialize(directory: str, bundled: str, transport) -> None:
    """Own one event loop for the Android process, outside Activity and WebView lifetimes."""
    global _runtime, _loop
    if _runtime is not None:
        return
    _loop = asyncio.new_event_loop()
    def run():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()
    threading.Thread(target=run, name='game-engine', daemon=True).start()
    async def create():
        global _runtime
        _runtime = Runtime(directory, bundled, transport)
    asyncio.run_coroutine_threadsafe(create(), _loop).result()


def command(encoded: str) -> str:
    """Return only public game DTOs or safe failures across the Java bridge."""
    try:
        result = asyncio.run_coroutine_threadsafe(_runtime.command(json.loads(encoded)), _loop).result()
        return json.dumps({'data': result}, ensure_ascii=False)
    except GameError as error:
        return json.dumps({'error': error.detail, 'status': error.status_code}, ensure_ascii=False)
    except Exception:
        return json.dumps({'error': '本地引擎操作失败', 'status': 500}, ensure_ascii=False)
