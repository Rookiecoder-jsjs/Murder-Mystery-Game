const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/context/game-reducer.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { gameReducer, initialState } = context.exports;
const history = [{ speaker: '甲', message: '我的介绍' }];
const payload = {
  gameId: 'new-game',
  status: { story_id: 'story', phase: 'introduction', mode: 'quick', round: 1, max_rounds: 3,
    game_ended: false, winner: null, is_speaking: false, investigation_options: [], available_actions: [],
    characters: [], player: { id: 'human' } },
  clueBoard: { clues: [], scene_public_clues: [], accusation_points: 1 }, history,
};
test('refreshing the introduction retains statements and lets the player continue', () => {
  const state = gameReducer(initialState, { type: 'GAME_RESUMED', payload });
  assert.equal(state.introductions, history);
  assert.equal(state.storyId, 'story');
});
test('loading the verdict restores the winner and finished state', () => {
  let state = gameReducer(initialState, { type: 'GAME_RESUMED', payload: {
    ...payload, status: { ...payload.status, phase: 'reveal', game_ended: true, winner: 'good' },
  } });
  state = gameReducer(state, { type: 'SET_REVEAL_INFO', payload: { winner: 'good' } });
  assert.equal(state.winner, 'good');
  assert.equal(state.gameEnded, true);
});
test('resuming another game clears the previous verdict and introductions', () => {
  const state = gameReducer({ ...initialState, revealInfo: { winner: 'killer' }, winner: 'killer',
    gameEnded: true, introductions: history }, { type: 'GAME_RESUMED', payload: {
      ...payload, status: { ...payload.status, phase: 'investigation' },
  } });
  assert.equal(state.revealInfo, null);
  assert.equal(state.winner, null);
  assert.equal(state.gameEnded, false);
  assert.equal(state.introductions.length, 0);
});
test('resuming during a background response keeps send and transition controls busy', () => {
  const state = gameReducer(initialState, { type: 'GAME_RESUMED', payload: {
    ...payload, status: { ...payload.status, phase: 'discussion', is_speaking: true },
  } });
  assert.equal(state.isSpeaking, true);
});

function client(streamText, native = { isAndroid: false, NativeError: class NativeError extends Error {} }) {
  const source = fs.readFileSync(path.join(__dirname, '../src/api/client.ts'), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const context = { exports: {}, AbortController, DOMException, TextDecoder,
    require: (name) => {
      assert.equal(name, './native');
      return native;
    },
    window: { setTimeout, clearTimeout },
    fetch: async () => new Response(streamText, { status: 200 }),
  };
  vm.runInNewContext(compiled, context);
  return context.exports.api;
}
test('SSE EOF without a done event is an error, so callers resynchronize', async () => {
  const api = client('event: message\ndata: {"speaker":"AI","message":"回复"}\n\n');
  const stream = api.speakStream('game', '问题');
  assert.equal((await stream.next()).value.message, '回复');
  await assert.rejects(stream.next(), /连接提前中断/);
});
test('SSE accepts the message and terminal phase from a completed round', async () => {
  const api = client('event: message\ndata: {"speaker":"AI","message":"回复"}\n\nevent: done\ndata: {"phase":"discussion"}\n\n');
  const stream = api.speakStream('game', '问题');
  assert.equal((await stream.next()).value.message, '回复');
  const done = await stream.next();
  assert.equal(done.done, true);
  assert.equal(done.value, 'discussion');
});

test('Android dispatches reads, actions and discussion through the native engine', async () => {
  const calls = [];
  const native = {
    isAndroid: true,
    nativeRequest: async (endpoint, options) => { calls.push([endpoint, options]); return { game_id: 'phone-game' }; },
    nativeSpeak: async function* (id, body) { calls.push([id, body]); yield { speaker: 'AI', message: '本地回复' }; return 'discussion'; },
  };
  const api = client('', native);
  await api.listStories();
  const game = await api.loadGame('saved', 'quick');
  assert.equal(game.game_id, 'phone-game');
  assert.equal(calls[0][0], '/stories');
  assert.equal(calls[1][0], '/games/load');
  assert.equal(JSON.parse(calls[1][1].body).mode, 'quick');
  const stream = api.speakStream('phone-game', '问题');
  assert.equal((await stream.next()).value.message, '本地回复');
  assert.equal((await stream.next()).value, 'discussion');
  assert.equal(calls[2][0], 'phone-game');
});
