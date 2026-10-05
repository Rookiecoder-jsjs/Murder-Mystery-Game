const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/api/storyLibrary.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const calls = [];
const context = { exports: {}, require: () => ({ gameEngine: {
  libraryCommand: async options => { calls.push(options); return { id: 'content-task' }; },
} }) };
vm.runInNewContext(compiled, context);
const { libraryApi, isLibraryTaskActive, libraryTaskLabel, contentSize } = context.exports;
test('install sends only pinned content identity, with no model configuration', async () => {
  await libraryApi.install({ id: 'story-id', latest_version: 2, sha256: 'digest', apiKey: 'must-not-send' });
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])), {
    kind: 'install', body: { story_id: 'story-id', content_version: 2, expected_sha256: 'digest' },
  });
});
test('only active download stages keep polling; local import and errors have correct labels', () => {
  for (const state of ['queued', 'checking', 'downloading', 'verifying', 'installing']) assert.equal(isLibraryTaskActive({ state }), true);
  for (const state of ['complete', 'failed', 'cancelled', 'interrupted']) assert.equal(isLibraryTaskActive({ state }), false);
  assert.equal(libraryTaskLabel({ state: 'downloading', kind: 'file' }), '正在读取内容包');
  assert.equal(libraryTaskLabel({ state: 'failed', error: '空间不足' }), '空间不足');
  assert.equal(contentSize(0), '0 KB');
});
