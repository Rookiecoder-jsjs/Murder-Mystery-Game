'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { readyPort } = require('./backend-ready');

test('ignores stale files and wrong live servers; accepts only the launched ready backend', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'murder-ready-'));
  const file = path.join(dir, '.port.json');
  let health = { launch_id: 'old', pid: 12 };
  const server = http.createServer((_req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(health));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { await new Promise((resolve) => server.close(resolve)); await fs.rm(dir, { recursive: true }); });
  const port = server.address().port;
  await fs.writeFile(file, JSON.stringify({ backend_port: port, launch_id: 'old', pid: 12 }));
  assert.equal(await readyPort(file, 'current', 42), null);
  await fs.writeFile(file, JSON.stringify({ backend_port: port, launch_id: 'current', pid: 42 }));
  assert.equal(await readyPort(file, 'current', 42), null);
  health = { launch_id: 'current', pid: 42 };
  assert.equal(await readyPort(file, 'current', 42), port);
  await fs.writeFile(file, '{');
  assert.equal(await readyPort(file, 'current', 42), null);
});

test('port publication before HTTP listen is not readiness', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'murder-ready-'));
  t.after(() => fs.rm(dir, { recursive: true }));
  const file = path.join(dir, '.port.json');
  const server = http.createServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(file, JSON.stringify({ backend_port: port, launch_id: 'current', pid: 42 }));
  assert.equal(await readyPort(file, 'current', 42), null);
});
