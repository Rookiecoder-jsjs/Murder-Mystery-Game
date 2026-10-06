const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const status = (id, phase = 'introduction') => ({ story_id: `story-${id}`, phase, game_ended: false,
  winner: null, is_speaking: false, mode: 'quick', round: 1, max_rounds: 3, characters: [],
  player: { id: 'human', name: '玩家' }, investigation_options: [], available_actions: [] });
const compile = name => ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/context', name), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function provider(overrides = {}) {
  const reducer = { exports: {} };
  vm.runInNewContext(compile('game-reducer.ts'), reducer);
  let state = reducer.exports.initialState;
  const refs = [];
  let cursor = 0;
  const api = { getGameStatus: async id => status(id),
    getClues: async () => ({ clues: [], scene_public_clues: [], accusation_points: 1 }),
    getDiscussionHistory: async () => ({ history: [] }), ...overrides };
  const context = { exports: {}, AbortController, crypto: { randomUUID: () => 'question' }, require: name => {
    if (name === 'react') return { useCallback: callback => callback,
      useRef: value => refs[cursor++] || (refs[cursor - 1] = { current: value }),
      useReducer: () => [state, action => { state = reducer.exports.gameReducer(state, action); }] };
    if (name === 'react/jsx-runtime') return { jsx: (_type, props) => props };
    if (name === '../api/client') return { api, ApiError: Error };
    if (name === '../api/native') return { isAndroid: false };
    if (name === '../components/common') return { useToast: () => ({ notify() {} }) };
    if (name === './game-context') return { GameContext: { Provider: 'provider' } };
    if (name === './game-reducer') return reducer.exports;
    throw new Error(`Unexpected import ${name}`);
  } };
  vm.runInNewContext(compile('GameContext.tsx'), context);
  return { api, get state() { return state; }, render() {
    cursor = 0;
    return context.exports.GameProvider({ children: null }).value;
  } };
}

test('a late verdict cannot end another saved game or expose the old truth', async () => {
  const pending = deferred();
  const app = provider({ vote: () => pending.promise });
  await app.render().resumeGame('A');
  const original = app.render();
  const voting = original.vote('角色甲');
  await original.resumeGame('B');
  pending.resolve({ game_ended: true, winner: 'killer', reveal: { winner: 'killer', case_info: { title: 'A真相' } } });
  await voting;
  assert.equal(app.state.gameId, 'B');
  assert.equal(app.state.phase, 'introduction');
  assert.equal(app.state.gameEnded, false);
  assert.equal(app.state.revealInfo, null);
});

test('returning to the same ID still rejects results from its previous visit', async () => {
  const pending = deferred();
  const app = provider({ vote: () => pending.promise });
  await app.render().resumeGame('A');
  const voting = app.render().vote('角色甲');
  await app.render().resumeGame('B');
  await app.render().resumeGame('A');
  pending.resolve({ game_ended: true, winner: 'good', reveal: { winner: 'good' } });
  await voting;
  assert.equal(app.state.gameId, 'A');
  assert.equal(app.state.gameEnded, false);
});

test('late phase, investigation, introduction and accusation results do not change a new game', async () => {
  const actions = [ ['nextPhase', 'nextPhase'], ['startVoting', 'startVoting'],
    ['returnToInvestigation', 'returnToInvestigation'], ['startNextRound', 'nextInvestigationRound'],
    ['investigate', 'investigate'], ['introduce', 'introduce'], ['accuse', 'accuse'] ];
  for (const [action, apiName] of actions) {
    const pending = deferred();
    const app = provider({ [apiName]: () => pending.promise });
    await app.render().resumeGame('A');
    const operation = app.render()[action]('角色甲');
    await app.render().resumeGame('B');
    const before = JSON.stringify(app.state);
    pending.resolve({ phase: 'voting', round: 3, available_actions: ['vote'],
      clue_board: { clues: [{ id: 'old-clue' }], scene_public_clues: [], accusation_points: 0 },
      found: [{ id: 'old-clue' }], player_introduction: 'A开场', ai_introductions: [],
      game_ended: true, winner: 'killer', reveal: { winner: 'killer' } });
    await operation;
    assert.equal(JSON.stringify(app.state), before, action);
  }
});

test('an old failure cannot clear the new resume spinner or set its error', async () => {
  const action = deferred(), reading = deferred();
  const app = provider({ vote: () => action.promise, getGameStatus: id => id === 'B' ? reading.promise : Promise.resolve(status(id)) });
  await app.render().resumeGame('A');
  const voting = app.render().vote('角色甲');
  const resuming = app.render().resumeGame('B');
  action.reject(new Error('A保存失败'));
  await assert.rejects(voting, /A保存失败/);
  assert.equal(app.state.isLoading, true);
  assert.equal(app.state.error, null);
  reading.resolve(status('B'));
  await resuming;
  assert.equal(app.state.gameId, 'B');
});

test('late creation does not replace a resumed game; failed creation keeps the old game usable', async () => {
  const pending = deferred();
  const app = provider({ createGame: () => pending.promise,
    loadGame: async () => { throw new Error('开局失败'); },
    nextPhase: async () => ({ phase: 'investigation', available_actions: [] }) });
  await app.render().resumeGame('A');
  const creation = app.render().createGame('新故事');
  await app.render().resumeGame('B');
  pending.resolve({ game_id: 'C', characters: [], phase: 'introduction' });
  assert.equal(await creation, 'C');
  assert.equal(app.state.gameId, 'B');
  await assert.rejects(app.render().loadGame('missing'), /开局失败/);
  await app.render().nextPhase();
  assert.equal(app.state.gameId, 'B');
  assert.equal(app.state.phase, 'investigation');
});

test('current verdict and reveal still load; a reveal failure is surfaced for retry', async () => {
  let failed = true;
  const app = provider({ vote: async () => ({ game_ended: true, winner: 'good', reveal: { winner: 'good' } }),
    getReveal: async () => { if (failed) throw new Error('读取失败'); return { winner: 'good' }; } });
  await app.render().resumeGame('A');
  await assert.rejects(app.render().loadReveal(), /读取失败/);
  failed = false;
  await app.render().loadReveal();
  assert.equal(app.state.gameEnded, true);
  await app.render().vote('角色甲');
  assert.equal(app.state.winner, 'good');
});

test('reset invalidates outstanding completions', async () => {
  const pending = deferred();
  const app = provider({ vote: () => pending.promise });
  await app.render().resumeGame('A');
  const voting = app.render().vote('角色甲');
  app.render().resetGame();
  pending.resolve({ game_ended: true, winner: 'good', reveal: { winner: 'good' } });
  await voting;
  assert.equal(app.state.gameId, null);
  assert.equal(app.state.gameEnded, false);
});
