#!/usr/bin/env node
/**
 * Backend-only dev launcher. Use when you only want the FastAPI server
 * (e.g. for testing against a separate frontend).
 */

'use strict';

const { spawn } = require('node:child_process');
const path = require('node:path');

const BACKEND_DIR = path.resolve(__dirname, '..', 'backend');

const child = spawn('python', ['-m', 'app.main'], {
  cwd: BACKEND_DIR,
  stdio: 'inherit',
  shell: true,
  windowsHide: true,
});

child.on('exit', (code) => process.exit(code ?? 0));
process.on('SIGINT', () => child.kill('SIGTERM'));
process.on('SIGTERM', () => child.kill('SIGTERM'));
