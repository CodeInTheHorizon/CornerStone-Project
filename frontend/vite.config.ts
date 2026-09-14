import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const variables = loadEnv(mode, process.cwd(), 'VITE_')
  if (command === 'build' && process.env.VERCEL === '1') {
    const raw = variables.VITE_API_BASE_URL?.trim()
    let url: URL
    try {
      url = new URL(raw ?? '')
    } catch {
      throw new Error('Set VITE_API_BASE_URL to the deployed HTTPS backend URL in Vercel before building.')
    }
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
      throw new Error('VITE_API_BASE_URL must be a public HTTPS backend URL without credentials, query or fragment.')
    }
  }
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      port: 5173,
      strictPort: true,
    },
  }
})
