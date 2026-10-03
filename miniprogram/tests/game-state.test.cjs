const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function provider() {
  let state, contextValue;
  const refs = [];
  let refIndex = 0;
  const api = {
    createGame: async () => ({ game_id: 'game', story_id: 'story', phase: 'introduction', player: { id: 'human' }, characters: [] }),
    getStatus: async () => ({ story_id: 'story', phase: 'introduction', mode: 'classic', round: 1, max_rounds: 5,
      game_ended: false, winner: null, is_speaking: false, player: { id: 'human' }, characters: [],
      investigation_options: [], available_actions: [] }),
    getClues: async () => ({ clues: [{ id: 'initial' }], scene_public_clues: [], accusation_points: 1 }),
    getDiscussionHistory: async () => ({ history: [] }),
    introduce: async () => ({ player_introduction: '你好', ai_introductions: [{ speaker: 'AI', message: '介绍' }] }),
    nextPhase: async () => ({ phase: 'investigation', round: 1, available_actions: ['discuss'] }),
  };
  const modules = {
    react: { createContext: () => ({ Provider: 'Provider' }), useCallback: f => f, useMemo: f => f(),
      useRef: initial => refs[refIndex++] ||= { current: initial },
      useReducer: (reducer, initial) => { state ||= initial; return [state, action => { state = reducer(state, action); }]; } },
    'react/jsx-runtime': { jsx: (_type, props) => { contextValue = props.value; return props; } },
    '@tarojs/taro': { default: { setStorageSync() {}, removeStorageSync() {} } },
    '@/services/game-api': { gameApi: api }, '@/services/http': { ApiError: Error },
  };
  const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/store/game-context.tsx'), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const env = { exports: {}, require: id => modules[id] };
  vm.runInNewContext(compiled, env);
  return { api, state: () => state, render: () => { refIndex = 0; env.exports.GameProvider({ children: null }); return contextValue; } };
}
test('new games fetch their initial evidence; entering investigation retains it', async () => {
  const app = provider();
  await app.render().createGame('主题');
  assert.equal(app.state().clues[0].id, 'initial');
  await app.render().introduce('你好');
  await app.render().nextPhase();
  assert.equal(app.state().clues[0].id, 'initial');
  assert.equal(app.state().discussionHistory.length, 2);
});
test('returning to investigation reads evidence after the backend has distributed it', async () => {
  const app = provider();
  await app.render().createGame('主题');
  const order = [];
  app.api.returnToInvestigation = async () => {
    await new Promise(resolve => setTimeout(resolve, 10));
    order.push('mutate');
    return { phase: 'investigation', round: 1, available_actions: ['discuss'] };
  };
  app.api.getClues = async () => {
    order.push('read');
    return { clues: order[0] === 'mutate' ? [{ id: 'new' }] : [], scene_public_clues: [], accusation_points: 1 };
  };
  await app.render().returnToInvestigation();
  assert.deepEqual(order, ['mutate', 'read']);
  assert.equal(app.state().clues[0].id, 'new');
});
test('restoring another game drops the cached verdict and restores recorded introductions', async () => {
  const app = provider();
  await app.render().createGame('主题');
  app.api.getReveal = async () => ({ winner: 'killer', characters: [], case_info: { title: '旧案件' } });
  await app.render().loadReveal('game');
  assert.equal(app.state().revealInfo.winner, 'killer');
  app.api.getStatus = async () => ({ story_id: 'other', phase: 'introduction', mode: 'quick', round: 1,
    max_rounds: 3, game_ended: false, winner: null, is_speaking: false,
    characters: [], player: { id: 'human' }, investigation_options: [], available_actions: [] });
  app.api.getDiscussionHistory = async () => ({ history: [{ speaker: 'AI', message: '已保存介绍' }] });
  await app.render().resumeGame('other-game');
  assert.equal(app.state().revealInfo, null);
  assert.equal(app.state().storyId, 'other');
  assert.equal(app.state().introductions.length, 1);
});

test('an older poll cannot replace the phase after a new player action', async () => {
  const app = provider();
  await app.render().createGame('主题');
  const previousStatus = app.api.getStatus;
  let release;
  app.api.getStatus = async () => {
    const old = await previousStatus();
    await new Promise(resolve => { release = resolve; });
    return old;
  };
  const poll = app.render().refreshGame();
  await new Promise(resolve => setImmediate(resolve));
  await app.render().nextPhase();
  release();
  await poll;
  assert.equal(app.state().phase, 'investigation');
});
