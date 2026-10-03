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
    },
  },
}))
