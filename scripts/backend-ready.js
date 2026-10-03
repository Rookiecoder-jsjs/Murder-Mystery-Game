'use strict';

const fs = require('node:fs/promises');
const http = require('node:http');

/** Only accept the backend started by this launcher, after HTTP is ready. */
async function readyPort(portFile, launchId, pid) {
  try {
    const data = JSON.parse(await fs.readFile(portFile, 'utf8'));
    const port = data.backend_port;
    if (data.launch_id !== launchId || data.pid !== pid ||
        !Number.isInteger(port) || port < 1 || port > 65535) return null;
    return await new Promise((resolve) => {
      const request = http.get({ hostname: '127.0.0.1', port, path: '/', timeout: 800 }, (response) => {
        let body = '';
        response.on('data', (chunk) => {
          body += chunk;
          if (body.length > 4096) request.destroy();
        });
        response.on('error', () => resolve(null));
        response.on('end', () => {
          try {
            const health = JSON.parse(body);
            resolve(response.statusCode === 200 && health.launch_id === launchId &&
              health.pid === pid ? port : null);
          } catch { resolve(null); }
        });
      });
      request.on('timeout', () => request.destroy());
      request.on('error', () => resolve(null));
    });
  } catch { return null; }
}

module.exports = { readyPort };
