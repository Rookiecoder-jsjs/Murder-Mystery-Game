#!/usr/bin/env node
/**
 * Cross-platform dev launcher.
 *
 * Starts the FastAPI backend first and waits for it to write
 * ``backend/.port.json`` (so the Vite dev server can proxy to the
 * right port), then starts the frontend.
 *
 * Robustness notes:
 * - Preflight: verifies that the frontend has been installed
 *   (``frontend/node_modules``) and that the Python deps are
 *   importable. If something is missing, prints a clear fix-it
 *   message and exits 2 BEFORE spawning anything.
 * - Vite is invoked via ``node node_modules/vite/bin/vite.js`` —
 *   bypassing the npm/shell PATH dance that breaks on Windows
 *   when spawning via ``shell: true``.
 * - Ctrl+C terminates both children (SIGTERM, then SIGKILL).
 *
 * No external dependencies — only Node.js built-ins.
 */

'use strict';

const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.resolve(__dirname, '..');
const BACKEND_DIR = path.join(ROOT, 'backend');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const PORT_FILE = path.join(BACKEND_DIR, '.port.json');
const VITE_BIN = path.join(FRONTEND_DIR, 'node_modules', 'vite', 'bin', 'vite.js');

const PORT_FILE_TIMEOUT_MS = 30000;
const COLORS = { backend: 36, frontend: 35, main: 33, err: 31 }; // cyan / magenta / yellow / red

const children = [];
let exiting = false;

function tag(name, color) {
  return `\x1b[${color}m[${name}]\x1b[0m`;
}

function pipeLines(child, name, color) {
  const prefix = tag(name, color);
  let outBuf = '';
  let errBuf = '';

  const flush = (buf, stream) => {
    const lines = buf.split(/\r?\n/);
    const tail = lines.pop();
    for (const line of lines) {
      if (line) stream.write(`${prefix} ${line}\n`);
    }
    return tail ?? '';
  };

  child.stdout.on('data', (chunk) => {
    outBuf += chunk.toString();
    outBuf = flush(outBuf, process.stdout);
  });
  child.stderr.on('data', (chunk) => {
    errBuf += chunk.toString();
    errBuf = flush(errBuf, process.stderr);
  });
  child.on('exit', () => {
    if (outBuf) process.stdout.write(`${prefix} ${outBuf}\n`);
    if (errBuf) process.stderr.write(`${prefix} ${errBuf}\n`);
  });
}

function startProcess(name, cmd, args, cwd) {
  const child = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: false,
    windowsHide: true,
  });
  pipeLines(child, name, COLORS[name] ?? 37);
  child.on('exit', (code, signal) => {
    console.log(tag(name, COLORS[name]), `exited (code=${code}, signal=${signal})`);
    shutdown(typeof code === 'number' ? code : 0);
  });
  child.on('error', (err) => {
    console.error(tag(name, COLORS.err), `failed to start: ${err.message}`);
    shutdown(1);
  });
  children.push(child);
  return child;
}

function shutdown(code = 0) {
  if (exiting) return;
  exiting = true;
  for (const child of children) {
    try { child.kill('SIGTERM'); } catch (_) { /* ignore */ }
  }
  setTimeout(() => {
    for (const child of children) {
      try { child.kill('SIGKILL'); } catch (_) { /* ignore */ }
    }
    process.exit(code);
  }, 1500).unref();
}

process.on('SIGINT', () => {
  console.log(tag('main', COLORS.main), 'SIGINT — shutting down');
  shutdown(0);
});
process.on('SIGTERM', () => shutdown(0));

// --- Preflight: ensure dependencies are present ----------------------------

const errors = [];

if (!fs.existsSync(path.join(FRONTEND_DIR, 'node_modules'))) {
  errors.push(
    `Frontend deps not installed. Run: cd frontend && npm install`,
  );
} else if (!fs.existsSync(VITE_BIN)) {
  errors.push(
    `Vite binary missing at ${path.relative(ROOT, VITE_BIN)}. ` +
    `Re-run: cd frontend && npm install`,
  );
}

const pyProbe = spawnSync(
  'python',
  ['-c', 'import fastapi, uvicorn, openai, pydantic, dotenv, numpy; import camel.agents'],
  { cwd: BACKEND_DIR, encoding: 'utf-8' },
);
if (pyProbe.status !== 0) {
  const detail = (pyProbe.stderr || pyProbe.stdout || '').trim().split(/\r?\n/).pop() ?? '';
  errors.push(
    `Python deps missing or import error: ${detail}\n` +
    `        Fix: cd backend && pip install -r requirements.txt`,
  );
}

if (errors.length) {
  console.error(tag('main', COLORS.err), 'preflight failed:');
  for (const e of errors) console.error('  -', e);
  process.exit(2);
}

// --- Backend first ---------------------------------------------------------

console.log(tag('main', COLORS.main), 'starting backend (python -m app.main)...');
startProcess('backend', 'python', ['-m', 'app.main'], BACKEND_DIR);

// --- Wait for port file, then start frontend -------------------------------

const waitStart = Date.now();
const poller = setInterval(() => {
  if (fs.existsSync(PORT_FILE)) {
    clearInterval(poller);
    try {
      const data = JSON.parse(fs.readFileSync(PORT_FILE, 'utf-8'));
      const elapsed = Date.now() - waitStart;
      console.log(
        tag('main', COLORS.main),
        `backend ready on port ${data.backend_port} (${elapsed}ms) — starting frontend`,
      );
    } catch (e) {
      console.log(tag('main', COLORS.main), 'backend port file unreadable — starting frontend anyway');
    }
    // Bypass the npm shell-PATH quirk on Windows: call the vite entry
    // script directly via node.
    startProcess('frontend', process.execPath, [VITE_BIN], FRONTEND_DIR);
    return;
  }
  if (Date.now() - waitStart > PORT_FILE_TIMEOUT_MS) {
    clearInterval(poller);
    console.error(
      tag('main', COLORS.main),
      `backend did not write ${path.relative(ROOT, PORT_FILE)} within ${PORT_FILE_TIMEOUT_MS}ms — starting frontend anyway`,
    );
    startProcess('frontend', process.execPath, [VITE_BIN], FRONTEND_DIR);
  }
}, 100);
