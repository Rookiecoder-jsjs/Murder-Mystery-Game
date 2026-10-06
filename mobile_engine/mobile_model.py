"""Narrow completion adapter: native transport owns credentials and HTTPS."""
import contextvars
import hashlib
import json
from types import SimpleNamespace
from app.core.errors import ModelInterrupted

operation = contextvars.ContextVar('mobile_operation', default=None)


def to_object(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k: to_object(v) for k, v in value.items()})
    if isinstance(value, list):
        return [to_object(v) for v in value]
    return value


class NativeModelClient:
    """Compatibility facade limited to the completions surface used by our engine."""
    def __init__(self, transport, store, timeout=180):
        self.transport, self.store, self.timeout = transport, store, timeout
        self.chat = self
        self.completions = self

    def with_options(self, timeout=180, **_options):
        return NativeModelClient(self.transport, self.store, timeout)

    def create(self, **kwargs):
        task = operation.get()
        if task is None:
            raise ModelInterrupted('模型调用缺少任务记录')
        payload = {k: v for k, v in kwargs.items() if v is not None and k != 'extra_body'}
        if task['settings'].get('thinking', True):
            payload.update(kwargs.get('extra_body') or {})
        payload['stream'] = False
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        destination = task['settings']['baseUrl']
        scoped = json.dumps({'base_url': destination, 'request': encoded}, sort_keys=True)
        key = task['id'] + ':' + hashlib.sha256(scoped.encode()).hexdigest()
        cached = self.store.get('calls', key)
        if cached is None and destination == task.get('legacy_cache_base_url', destination):
            # Pre-upgrade records belong only to the task's original service.
            legacy = task['id'] + ':' + hashlib.sha256(encoded.encode()).hexdigest()
            cached = self.store.get('calls', legacy)
            if cached is not None:
                self.store.put('calls', key, cached)
        reused = bool(cached and cached.get('response'))
        if cached and cached.get('response'):
            raw = cached['response']
        else:
            if not self.transport.isActive():
                raise ModelInterrupted('应用已切到后台，回到前台后可继续')
            # Each explicit continuation permits retrying an uncertain call once.
            if cached and cached.get('attempt') == task['attempt']:
                raise ModelInterrupted('该调用结果未确认，请检查网络后手动继续')
            self.store.put('calls', key, {'attempt': task['attempt'], 'state': 'sent'})
            try:
                raw = json.loads(str(self.transport.complete(
                    encoded, self.timeout, task['settings']['baseUrl'])))
            except Exception as exc:
                # Native exceptions contain a safe error category, never response bodies or headers.
                raise ModelInterrupted('模型连接中断，请检查网络和模型设置后继续') from exc
            if raw.get('error'):
                raise ModelInterrupted(str(raw['error']))
            if not raw.get('choices') or not isinstance(raw['choices'][0].get('message'), dict):
                raise ModelInterrupted('模型返回格式不兼容，请检查模型设置')
            self.store.put('calls', key, {'state': 'complete', 'response': raw})
        for choice in raw['choices']:
            choice['message'].setdefault('content', None)
            choice['message'].setdefault('tool_calls', None)
        result = to_object(raw)
        result.usage = dict(raw.get('usage') or {})
        result.usage['local_reused'] = reused
        return result
