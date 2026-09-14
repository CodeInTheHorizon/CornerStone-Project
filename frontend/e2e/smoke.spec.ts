/**
 * Harness smoke test, run per engine before the large specs:
 * SPA and backend reachable, login, dashboard visible, logout.
 */
import { test, expect } from '@playwright/test'
import { installNetworkDiagnostics, networkEvents } from './diagnostics'

const API = 'http://127.0.0.1:8184'

installNetworkDiagnostics()

test('smoke: frontend, backend, login, dashboard, logout', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))

  for (const path of ['/health', '/ready']) {
    const response = await request.get(API + path)
    expect(response.status(), path).toBe(200)
  }
  const shell = await request.get('/')
  expect(shell.status()).toBe(200)

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Welcome back', exact: true })).toBeVisible()
  await page.getByLabel('Email', { exact: true }).fill('viewer@example.com')
  await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
  const dashboardLoaded = Promise.all(['/analytics/summary', '/ml/status'].map((path) => page.waitForResponse((r) => new URL(r.url()).pathname === path)))
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('main')).toBeVisible()
  for (const response of await dashboardLoaded) expect(response.status(), response.url()).toBe(200)
  await expect(page.getByRole('main')).toContainText(/Stored Records\s*[1-9]\d*(?!\d)/)

  const logout = page.waitForResponse((r) => new URL(r.url()).pathname === '/auth/logout')
  await page.getByRole('button', { name: 'Logout', exact: true }).first().click()
  expect((await logout).status()).toBe(204)
  await expect(page).toHaveURL(/\/login$/)

  expect(errors).toEqual([])
  expect(networkEvents(page)).toEqual([])
})
