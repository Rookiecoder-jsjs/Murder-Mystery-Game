import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

function getBackendPort(): number {
  try {
    const portFile = path.resolve(__dirname, '../backend/.port.json')
    const data = JSON.parse(fs.readFileSync(portFile, 'utf-8'))
    return data.backend_port
  } catch {
    return 8000
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/stories': `http://localhost:${getBackendPort()}`,
      '/games': `http://localhost:${getBackendPort()}`,
      '/assets/portraits': `http://localhost:${getBackendPort()}`,
    },
  },
})
