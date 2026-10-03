const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

test('native polling emits only changed real stages, then returns the saved result', async () => {
  const events = [];
  const stage = { id: 'task', endpoint: '/games', state: 'running', progress: { stage: 'review', label: '正在审查真相与证据链' } };
  const replies = [stage, stage, { ...stage, state: 'done', result: { game_id: 'game' } }];
  const bridge = { command: async () => ({ data: replies.shift() }) };
  const context = { exports: {}, DOMException, Event,
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail; } },
    document: { hidden: false },
    window: { setTimeout: resolve => { resolve(); }, dispatchEvent: event => { events.push(event); } },
    require: () => ({ Capacitor: { getPlatform: () => 'android' }, registerPlugin: () => bridge }),
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/api/native.ts'), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText, context);
  const result = await context.exports.waitForTask('task');
  assert.equal(result.game_id, 'game');
  assert.equal(events.filter(e => e.type === 'mystery:task-progress').length, 1);
  assert.equal(events[0].detail.progress.stage, 'review');
  assert.equal(events[1].type, 'mystery:tasks');
});

test('completed discussion notifies the home task list after navigating away', async () => {
  const events = [];
  let historyReads = 0;
  const bridge = { command: async ({ command }) => {
    if (command.kind === 'start') return { data: {} };
    if (command.kind === 'task') return { data: { state: 'done', result: { phase: 'discussion' } } };
    historyReads += 1;
    return { data: { history: historyReads === 1 ? [] : [
      { speaker: '玩家', message: '提问' }, { speaker: '角色', message: '中文回答' },
    ] } };
  } };
  const context = { exports: {}, DOMException, Event, crypto: { randomUUID: () => 'task' },
    document: { hidden: false }, window: { dispatchEvent: event => { events.push(event); } },
    require: () => ({ Capacitor: { getPlatform: () => 'android' }, registerPlugin: () => bridge }),
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/api/native.ts'), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText, context);
  const stream = context.exports.nativeSpeak('game', { message: '提问' });
  assert.equal((await stream.next()).value.message, '提问');
  assert.equal((await stream.next()).value.message, '中文回答');
  assert.equal((await stream.next()).value, 'discussion');
  assert.equal(events[0].type, 'mystery:tasks');
});
