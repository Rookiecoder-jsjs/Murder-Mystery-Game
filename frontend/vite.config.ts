import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

function getBackendPort(): number {
  const launchedPort = Number(process.env.BACKEND_PORT)
  if (Number.isInteger(launchedPort) && launchedPort > 0 && launchedPort <= 65535) return launchedPort
  try {
    const portFile = path.resolve(__dirname, '../backend/.port.json')
    const data = JSON.parse(fs.readFileSync(portFile, 'utf-8'))
    return data.backend_port
  } catch {
    return 8000
  }
}

const backendTarget = `http://127.0.0.1:${getBackendPort()}`

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), {
    name: 'bundled-story-artwork',
    writeBundle(options) {
      const content = path.resolve(__dirname, '../backend/app/content');
      const manifest = JSON.parse(fs.readFileSync(path.join(content, 'stories/manifest.json'), 'utf8'));
      for (const name of manifest.packages) {
        if (typeof name !== 'string' || path.basename(name) !== name || !name.endsWith('.json')) throw new Error('Invalid story package filename');
        const story = JSON.parse(fs.readFileSync(path.join(content, 'stories', name), 'utf8'));
        if (!/^[a-f0-9-]{36}$/.test(story.archive.id)) throw new Error('Invalid artwork story ID');
        const artwork = story.artwork ?? {};
        if (artwork.retained_files && !Array.isArray(artwork.retained_files)) throw new Error('Invalid retained artwork list');
        const files = [artwork.cover, ...Object.values(artwork.portraits ?? {}), ...(artwork.retained_files ?? [])].filter(Boolean);
        for (const file of files) {
          if (typeof file !== 'string' || !/^[A-Za-z0-9_-]+\.webp$/.test(file)) throw new Error('Invalid artwork filename');
          const destination = path.resolve(__dirname, options.dir ?? 'dist', 'assets/story-library', story.archive.id, file);
          fs.mkdirSync(path.dirname(destination), { recursive: true });
          fs.copyFileSync(path.join(content, 'images', story.archive.id, file), destination);
        }
      }
    },
  }, {
    name: 'offline-android-fonts',
    transformIndexHtml(html) {
      return mode === 'android' ? html.replace(/<link\b[^>]*href="https:\/\/fonts\.[^>]*>/g, '') : html;
    },
  }],
  server: {
    proxy: {
      '/stories': backendTarget,
      '/games': backendTarget,
      '/assets/portraits': backendTarget,
      '/assets/story-library': backendTarget,
    },
  },
}))
