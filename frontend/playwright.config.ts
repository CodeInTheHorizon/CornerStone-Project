import { resolve } from 'node:path'
import { defineConfig } from '@playwright/test'

// Absolute, platform-native path: cmd.exe cannot run a POSIX-style relative executable path.
const python = resolve(import.meta.dirname, '..', 'backend', '.venv', 'Scripts', 'python.exe')

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'e2e-results.json' }], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5184', viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure', trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: ['chromium', 'firefox', 'webkit'].map(browserName => ({ name: browserName, use: { browserName: browserName as 'chromium' | 'firefox' | 'webkit' } })),
  webServer: { command: `"${python}" -B e2e/serve.py`, url: 'http://127.0.0.1:5184/login', timeout: 240_000, reuseExistingServer: process.env.PHASE14_REUSE_SERVER === '1' },
})
