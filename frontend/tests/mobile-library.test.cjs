const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/utils/mobileLibrary.ts'), 'utf8');
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
const { filterLibraryBooks, bookDisplay, latestBookTask, mobileBackTarget, hasBookUpdate } = context.exports;
const view = { query: '', filter: 'all', limit: 20, retainedIds: [] };
const books = [
  { id: 'c', title: '港口', installed_version: null, latest_version: 1, available: { title: '港口' } },
  { id: 'a', title: '雨夜旧版', installed_version: 1, latest_version: 2, compatible: false, available: { title: '雨夜新版', summary: '钟声' } },
  { id: 'b', title: '旅馆', installed_version: 1, latest_version: 1, available: { title: '旅馆' } },
];
const ids = values => Array.from(values, value => value.id);
test('download completion and a different native array order do not rearrange the catalogue', () => {
  assert.deepEqual(ids(filterLibraryBooks(books, view)), ['a', 'b', 'c']);
  const updated = [{ ...books[0], installed_version: 1 }, books[2], books[1]];
  assert.deepEqual(ids(filterLibraryBooks(updated, view)), ['a', 'b', 'c']);
  assert.deepEqual(ids(books), ['c', 'a', 'b']);
});
test('search covers both installed and available public metadata; incompatible updates remain discoverable', () => {
  assert.deepEqual(ids(filterLibraryBooks(books, { ...view, query: ' 钟声 ' })), ['a']);
  assert.deepEqual(ids(filterLibraryBooks(books, { ...view, filter: 'installed' })), ['a', 'b']);
  assert.deepEqual(ids(filterLibraryBooks(books, { ...view, filter: 'updates' })), ['a']);
  assert.equal(hasBookUpdate(books[1]), true);
});
test('a completed update stays in its filtered row until the user changes the view', () => {
  const done = [{ ...books[1], installed_version: 2 }];
  assert.deepEqual(ids(filterLibraryBooks(done, { ...view, filter: 'updates', retainedIds: ['a'] })), ['a']);
  assert.deepEqual(ids(filterLibraryBooks(done, { ...view, filter: 'updates' })), []);
  assert.deepEqual(ids(filterLibraryBooks(done, { ...view, filter: 'updates', retainedIds: ['a'], query: '不存在' })), []);
});
test('a newer remote introduction never replaces the installed story used for play', () => {
  assert.equal(bookDisplay(books[1]), books[1]);
  assert.equal(bookDisplay(books[0]), books[0].available);
});
test('task selection uses the newest task for this story, independently of native array order', () => {
  const tasks = [{ kind: 'install', story_id: 'a', created: 2, id: 'new' }, { kind: 'file', story_id: 'a', created: 1, id: 'old' }, { kind: 'check', story_id: 'a', created: 3 }];
  assert.equal(latestBookTask(tasks, 'a').id, 'new');
  assert.equal(latestBookTask(tasks, 'unknown'), undefined);
});
test('Android detail deep links and personal stories have safe parents without browser history', () => {
  assert.equal(mobileBackTarget('/library/a'), '/library');
  assert.equal(mobileBackTarget('/library/a', { from: '/my/stories' }), '/my/stories');
  assert.equal(mobileBackTarget('/library/a', { from: 'https://example.com' }), '/library');
  assert.equal(mobileBackTarget('/library/a', { from: '/game/old' }), '/library');
  assert.equal(mobileBackTarget('/my/create'), '/my');
  assert.equal(mobileBackTarget('/library'), '/');
  assert.equal(mobileBackTarget('/game/old'), '/');
});
