const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/utils/discussionDraft.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const calls = [];
let saved = '';
const context = { exports: {}, require: () => ({ isAndroid: true, gameEngine: { draft: async ({ value }) => {
  if (value !== undefined) { calls.push(value); await new Promise(resolve => setTimeout(resolve, 5)); saved = value; }
  return { value: saved };
} } }) };
vm.runInNewContext(compiled, context);
const { decodeDiscussionDraft, saveDiscussionDraft, loadDiscussionDraft } = context.exports;

test('legacy draft text is preserved and new drafts restore target, evidence and pending question', () => {
  assert.equal(decodeDiscussionDraft('原来的中文问题').message, '原来的中文问题');
  assert.equal(decodeDiscussionDraft('').message, '');
  assert.equal(decodeDiscussionDraft('', 'char_3').targetId, 'char_3');
  const draft = { version: 1, message: '请解释这条证据', targetId: 'char_3', evidenceId: 'clue_4', pendingActionId: 'question-id' };
  assert.equal(JSON.stringify(decodeDiscussionDraft(JSON.stringify(draft))), JSON.stringify(draft));
  assert.equal(decodeDiscussionDraft('{"message":"玩家原文"}').message, '{"message":"玩家原文"}');
});

test('rapid edits and subsequent read wait for writes in order', async () => {
  const base = { version: 1, message: '第一稿', targetId: 'char_2', evidenceId: 'clue_1' };
  const first = saveDiscussionDraft('ordered-game', base);
  const second = saveDiscussionDraft('ordered-game', { ...base, message: '第二稿' });
  const restored = await loadDiscussionDraft('ordered-game');
  await Promise.all([first, second]);
  assert.equal(restored.message, '第二稿');
  assert.equal(restored.evidenceId, 'clue_1');
  assert.deepEqual(calls.map(value => JSON.parse(value).message), ['第一稿', '第二稿']);
});
