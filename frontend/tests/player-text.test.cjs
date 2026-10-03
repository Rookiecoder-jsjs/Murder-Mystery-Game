const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/utils/playerText.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { presentPlayerMessage, clueTitle, visibleClues } = context.exports;
const clue = { id: 'clue_11', type: 'document', content: '电话记录：八时三十五分，公馆拨往街角电话。' };
test('canonical question metadata displays evidence names without altering original words', () => {
  const original = '【询问林女士】Explain the timing.\n【出示证据】clue_11';
  const display = presentPlayerMessage(original, [clue]);
  assert.equal(display.text, 'Explain the timing.');
  assert.equal(display.target, '林女士');
  assert.equal(display.evidence[0], '电话记录');
  assert.ok(original.endsWith('clue_11'));
});
test('ordinary user quotation is preserved, unknown evidence does not expose an ID', () => {
  const text = '他说【出示证据】是什么意思？';
  assert.equal(presentPlayerMessage(text, []).text, text);
  assert.equal(presentPlayerMessage('问题\n【出示证据】clue_missing', []).evidence[0], '已出示的证据');
});
test('public and owned evidence merge once, names come only from visible content', () => {
  assert.equal(visibleClues([clue, clue]).length, 1);
  assert.equal(clueTitle(clue), '电话记录');
  assert.equal(clueTitle({ type: 'physical', content: '' }), '物证');
  assert.equal(clueTitle({ ...clue, title: '街角电话' }), '街角电话');
});
