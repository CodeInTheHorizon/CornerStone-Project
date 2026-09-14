/**
 * Phase 14 journeys that complement verification.spec.ts: administrator effects,
 * analyst/viewer denials, deep links, network failures, keyboard-only use,
 * focus visibility, request cleanliness, chart text alternatives and form errors.
 * Runs against the isolated backend and SPA started by e2e/serve.py.
 */
import { test, expect, type Page } from '@playwright/test'
import { installNetworkDiagnostics, isWebKitNavigationCancelReport } from './diagnostics'

installNetworkDiagnostics()

const API = 'http://127.0.0.1:8184'
const APP = 'http://127.0.0.1:5184'
const SIGNING_KEY = 'phase14-isolated-test-signing-key-never-deploy'

async function signIn(page: Page, email: string, destination = '/dashboard') {
  await page.goto(destination)
  await expect(page.getByRole('heading', { name: 'Welcome back', exact: true })).toBeVisible()
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(APP + destination)
  await expect(page.getByRole('main')).toBeVisible()
}
const token = (page: Page) => page.evaluate(() => localStorage.getItem('marketpulse-token'))
async function api(page: Page, path: string, init: { method?: string; data?: object; multipart?: Record<string, { name: string; mimeType: string; buffer: Buffer }> } = {}) {
  return page.request.fetch(API + path, { method: init.method ?? 'GET', headers: { Authorization: 'Bearer ' + await token(page) }, data: init.data, multipart: init.multipart })
}
async function adminHeaders(page: Page) {
  const response = await page.request.post(API + '/auth/login', { data: { email: 'administrator@example.com', password: 'marketpulse1' } })
  expect(response.status()).toBe(200)
  return { Authorization: 'Bearer ' + (await response.json()).access_token }
}
async function registerAccount(page: Page, label: string) {
  const email = `${label}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`
  const response = await page.request.post(API + '/auth/register', { data: { email, password: 'marketpulse1' } })
  expect(response.status()).toBe(201)
  return { email, id: (await response.json()).user.id as number }
}
/** Cancellation reasons per engine: Chromium, Firefox, WebKit. */
const CANCELLED = /^net::ERR_ABORTED$|^NS_BINDING_ABORTED$|cancelled/i

/**
 * Every console error and failed request, so each journey can assert a clean run.
 * A request cancelled because the test navigated the page (goto/reload while it was in
 * flight) is browser behaviour, not an app failure, and is skipped: it must carry a
 * cancellation reason AND have started before the latest test-initiated navigation began.
 * Browser event order is not reliable for this (Firefox/WebKit report the navigation
 * request after the cancellations it causes), so navigation start is recorded by the test.
 */
function watch(page: Page) {
  const problems: string[] = []
  let navigationStartedAt = -Infinity
  for (const method of ['goto', 'reload'] as const) {
    const original = page[method].bind(page) as (...args: unknown[]) => Promise<unknown>
    ;(page as unknown as Record<string, unknown>)[method] = (...args: unknown[]) => {
      navigationStartedAt = Date.now()
      return original(...args)
    }
  }
  page.on('pageerror', (error) => {
    // See isWebKitNavigationCancelReport: only after a test-initiated navigation.
    if (Number.isFinite(navigationStartedAt) && isWebKitNavigationCancelReport(error)) return
    problems.push('pageerror: ' + error.message)
  })
  page.on('console', (message) => { if (message.type() === 'error') problems.push('console: ' + message.text()) })
  page.on('response', (response) => { if (response.status() >= 400) problems.push(`${response.request().method()} ${response.url()} -> ${response.status()}`) })
  page.on('requestfailed', (request) => {
    const reason = request.failure()?.errorText ?? 'unknown'
    // timing().startTime is wall-clock ms from the browser; -1 when the engine did not record it.
    const started = request.timing().startTime
    const startedBeforeNavigation = started === -1 ? Number.isFinite(navigationStartedAt) : started <= navigationStartedAt
    if (CANCELLED.test(reason) && startedBeforeNavigation) return
    problems.push(`${request.method()} ${request.url()} failed: ${reason}`)
  })
  return problems
}
const tinyImport = () => ({ name: 'history.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify([{ platform: 'amazon', product_name: 'Denied import', price: 1, collection_timestamp: '2026-09-01T00:00:00Z' }])) })

test.describe('RBAC in the browser', () => {
  test('viewer sees own empty history and cannot mutate; direct 403s keep the session', async ({ page }) => {
    const problems = watch(page)
    await signIn(page, 'viewer@example.com')
    await expect(page.getByText('viewer@example.com · viewer').first()).toBeAttached()
    await expect(page.getByRole('link', { name: 'Datasets / Model Status' }).first()).toBeAttached()

    await page.goto('/dashboard/predictor')
    await expect(page.getByRole('heading', { name: 'Your recent predictions' })).toBeVisible()
    await expect(page.getByText('No saved predictions yet.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Make Prediction', exact: true })).toBeDisabled()

    await page.goto('/dashboard/marketplace-data')
    for (const name of ['Import file', 'Load demo dataset', 'Refresh Market Data']) {
      await expect(page.getByRole('button', { name, exact: true })).toBeDisabled()
    }
    await expect(page.getByText(/You do not have permission to perform this action\. Your role: viewer\./).first()).toBeVisible()

    for (const [path, init] of [
      ['/data/import', { method: 'POST', multipart: { file: tinyImport() } }],
      ['/data/demo/load', { method: 'POST' }],
      ['/data/collect', { method: 'POST', data: { platform: 'flipkart', keyword: 'earbuds' } }],
      ['/ml/dataset/build', { method: 'POST', data: {} }],
      ['/ml/train', { method: 'POST', data: { source_types: ['demo'] } }],
      ['/ml/predict', { method: 'POST', data: { product_key: 'x' } }],
      ['/admin/users', { method: 'GET' }],
    ] as const) {
      expect((await api(page, path, init)).status(), path).toBe(403)
    }
    await page.reload()
    await expect(page).toHaveURL(/marketplace-data$/)
    await expect(page.getByRole('main')).toBeVisible()
    expect(problems).toEqual([])
  })

  test('analyst builds and predicts but import, demo, LIVE refresh and training are denied', async ({ page }) => {
    await signIn(page, 'analyst@example.com', '/dashboard/marketplace-data')
    for (const name of ['Import file', 'Load demo dataset', 'Refresh Market Data']) {
      await expect(page.getByRole('button', { name, exact: true })).toBeDisabled()
    }
    await page.goto('/dashboard/train')
    await expect(page.getByRole('button', { name: 'Build Dataset', exact: true })).toBeEnabled()
    await expect(page.getByRole('button', { name: 'Train Model', exact: true })).toBeDisabled()
    await page.goto('/dashboard/predictor')
    const predict = page.getByRole('button', { name: 'Make Prediction', exact: true })
    // Disabled until a product is chosen, for every role; the permission shows once one is selected.
    await expect(predict).toBeDisabled()
    await page.getByLabel('Product / accessory', { exact: true }).selectOption({ index: 1 })
    await expect(predict).toBeEnabled()
    for (const [path, init] of [
      ['/data/import', { method: 'POST', multipart: { file: tinyImport() } }],
      ['/data/collect', { method: 'POST', data: { platform: 'flipkart', keyword: 'earbuds' } }],
      ['/ml/train', { method: 'POST', data: { source_types: ['demo'] } }],
      ['/admin/users', { method: 'GET' }],
    ] as const) {
      expect((await api(page, path, init)).status(), path).toBe(403)
    }
    await page.reload()
    await expect(page.getByRole('button', { name: 'Make Prediction', exact: true })).toBeVisible()
  })

  test('administrator has every operational control and role changes take effect', async ({ page, browser }) => {
    await signIn(page, 'administrator@example.com', '/dashboard/marketplace-data')
    await expect(page.getByText('administrator@example.com · administrator').first()).toBeAttached()
    await expect(page.getByRole('button', { name: 'Load demo dataset', exact: true })).toBeEnabled()
    await page.goto('/dashboard/train')
    await expect(page.getByRole('button', { name: 'Build Dataset', exact: true })).toBeEnabled()
    await expect(page.getByRole('link', { name: 'Train Model' }).first()).toBeAttached()
    const users = await api(page, '/admin/users')
    expect(users.status()).toBe(200)
    expect(JSON.stringify(await users.json())).not.toMatch(/hashed_password|token_version/)

    // Admin UI does not exist (Phase 13 is API-only); verify the effect of the admin API in a second browser session.
    const account = await registerAccount(page, 'promoted')
    const promoted = await api(page, `/admin/users/${account.id}/role`, { method: 'PATCH', data: { role: 'analyst' } })
    expect(promoted.status()).toBe(200)
    const other = await browser.newPage()
    await signIn(other, account.email, '/dashboard/train')
    await expect(other.getByRole('button', { name: 'Build Dataset', exact: true })).toBeEnabled()
    await expect(other.getByRole('button', { name: 'Train Model', exact: true })).toBeDisabled()
    // Status loading has finished (seeded model shows its quality) before the role changes underneath this session.
    await expect(other.getByRole('heading', { name: 'Model quality', exact: true })).toBeVisible()
    await expect(other.getByText('Loading dataset and model status…')).toHaveCount(0)

    expect((await api(page, `/admin/users/${account.id}/role`, { method: 'PATCH', data: { role: 'operator' } })).status()).toBe(200)
    await other.reload()
    await expect(other).toHaveURL(/login$/)
    await expect(other.getByRole('alert')).toContainText(/session/i)
    await signIn(other, account.email, '/dashboard/train')
    await expect(other.getByRole('button', { name: 'Train Model', exact: true })).toBeVisible()
    await expect(other.getByText(`${account.email} · operator`).first()).toBeAttached()
    await other.close()
  })
})

test.describe('sessions and routing', () => {
  test('protected deep links, refresh and unknown routes', async ({ page }) => {
    const problems = watch(page)
    await page.goto('/dashboard/predictor')
    await expect(page).toHaveURL(/login$/)
    await signIn(page, 'analyst@example.com', '/dashboard/predictor')
    for (const path of ['/dashboard', '/dashboard/marketplace-data', '/dashboard/train', '/dashboard/predictor', '/dashboard/trends', '/dashboard/analytics']) {
      await page.goto(path)
      await page.reload()
      await expect(page).toHaveURL(APP + path)
      await expect(page.getByRole('main')).toBeVisible()
    }
    await page.goto('/no-such-page')
    await expect(page).toHaveURL(APP + '/')
    await page.goto('/login')
    await expect(page).toHaveURL(/dashboard$/)
    expect(problems).toEqual([])
  })

  test('disabled account is signed out with an explanation and cannot sign back in', async ({ page }) => {
    const account = await registerAccount(page, 'disabled')
    const dashboardLoaded = Promise.all(['/analytics/summary', '/ml/status'].map((path) => page.waitForResponse((r) => new URL(r.url()).pathname === path)))
    await signIn(page, account.email)
    await dashboardLoaded
    const headers = await adminHeaders(page)
    expect((await page.request.patch(`${API}/admin/users/${account.id}/status`, { headers, data: { is_active: false } })).status()).toBe(200)
    await page.goto('/dashboard/analytics')
    await expect(page).toHaveURL(/login$/)
    await expect(page.getByRole('alert')).toContainText(/session/i)
    await page.getByLabel('Email', { exact: true }).fill(account.email)
    await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page).toHaveURL(/login$/)
  })

  test('401 during use returns to login; 5xx on session check keeps the token and explains', async ({ page }) => {
    // Let Trends' own summary request finish first; if the mock caught it before reload, the
    // pre-reload page would sign out and the reload would then discard the in-memory message.
    const summaryLoaded = page.waitForResponse((r) => new URL(r.url()).pathname === '/analytics/summary')
    await signIn(page, 'viewer@example.com', '/dashboard/trends')
    expect((await summaryLoaded).status()).toBe(200)
    await page.route('**/analytics/summary', (route) => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }))
    await page.reload()
    await expect(page).toHaveURL(/login$/)
    await expect(page.getByRole('alert')).toContainText(/session/i)
    await page.unroute('**/analytics/summary')

    await signIn(page, 'viewer@example.com')
    await page.route('**/auth/me', (route) => route.fulfill({ status: 503, json: { detail: 'Service temporarily unavailable' } }))
    await page.reload()
    await expect(page).toHaveURL(/login$/)
    await expect(page.getByRole('alert')).toContainText('Service temporarily unavailable')
    expect(await token(page)).not.toBeNull()
    await page.unroute('**/auth/me')
    await page.goto('/dashboard')
    await expect(page.getByRole('main')).toBeVisible()
  })

  test('backend offline: login and restore show a reachable-API message, never a blank screen', async ({ page }) => {
    await page.route(API + '/**', (route) => route.abort('connectionrefused'))
    await page.goto('/login')
    await page.getByLabel('Email', { exact: true }).fill('viewer@example.com')
    await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('Could not reach the API')
    await page.unroute(API + '/**')

    await signIn(page, 'viewer@example.com')
    await page.route(API + '/**', (route) => route.abort('connectionrefused'))
    await page.goto('/dashboard/analytics')
    await expect(page.getByRole('alert')).toContainText('Could not reach the API')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})

test.describe('keyboard and focus', () => {
  // Measured: Playwright's WebKit build leaves links out of the Tab order for both Tab and
  // Alt+Tab (Safari's default "Press Tab to highlight each item" off). WebKit therefore
  // verifies buttons, inputs and focus visibility, but cannot verify keyboard focus on links.
  const linksTabbable = (browserName: string) => browserName !== 'webkit'

  /** Tabs through the page and records any focused element that shows no focus indicator. */
  async function tabAndCheckFocus(page: Page, steps: number) {
    const missing: string[] = []
    for (let i = 0; i < steps; i++) {
      await page.keyboard.press('Tab')
      const state = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null
        if (!el || el === document.body) return null
        const style = getComputedStyle(el)
        const visible = style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2
        return { visible, name: `${el.tagName.toLowerCase()} ${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40)}` }
      })
      if (state && !state.visible) missing.push(state.name)
    }
    return missing
  }

  test('landing, login and dashboard work keyboard-only with visible focus', async ({ page, browserName }) => {
    await page.goto('/')
    if (linksTabbable(browserName)) {
      await page.keyboard.press('Tab')
      await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    }
    expect(await tabAndCheckFocus(page, 8)).toEqual([])

    await page.goto('/login')
    await page.getByLabel('Email', { exact: true }).focus()
    await page.keyboard.type('operator@example.com')
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Password', { exact: true })).toBeFocused()
    await page.keyboard.type('marketpulse1')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/dashboard$/)

    await page.goto('/dashboard/train')
    await expect(page.getByRole('button', { name: 'Build Dataset', exact: true })).toBeVisible()
    expect(await tabAndCheckFocus(page, 30)).toEqual([])

    // Toggle buttons respond to Space and expose their state.
    const demo = page.getByRole('group', { name: 'Source types', exact: true }).first().getByRole('button', { name: 'DEMO', exact: true })
    await demo.focus()
    await page.keyboard.press('Space')
    await expect(demo).toHaveAttribute('aria-pressed', 'false')
    await page.keyboard.press('Enter')
    await expect(demo).toHaveAttribute('aria-pressed', 'true')

    // Sidebar navigation by keyboard (desktop layout).
    const predictor = page.getByRole('navigation', { name: 'Dashboard' }).getByRole('link', { name: 'ML Predictor' })
    await predictor.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/predictor$/)
    const product = page.getByLabel('Product / accessory', { exact: true })
    await product.focus()
    await expect(product).toBeFocused()
    expect(await product.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none')
  })

  test('mobile drawer: Escape closes and returns focus; no trap after closing', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 })
    await signIn(page, 'viewer@example.com', '/dashboard/analytics')
    const open = page.getByRole('button', { name: 'Open navigation', exact: true })
    await open.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: 'Dashboard navigation' })
    await expect(dialog).toBeVisible()
    const box = await dialog.locator('nav').boundingBox()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(360)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(open).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.locator('main :focus, header :focus').first()).toBeAttached()
  })
})

test.describe('cleanliness, charts and validation', () => {
  test('production bundle and traffic: no dev localhost, no secrets, no stray hosts, no request loops', async ({ page }) => {
    const hosts = new Set<string>()
    const apiCalls: string[] = []
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (!url.protocol.startsWith('data')) hosts.add(url.origin)
      if (url.origin === API) apiCalls.push(`${Date.now()} ${url.pathname}`)
    })
    const responses: string[] = []
    page.on('response', async (response) => {
      if (response.url().startsWith(API) && (response.headers()['content-type'] ?? '').includes('json')) responses.push(await response.text().catch(() => ''))
    })
    const html = await (await page.request.get(APP + '/')).text()
    const bundles = [...html.matchAll(/src="(\/assets\/[^"]+\.js)"/g)].map((match) => match[1])
    expect(bundles.length).toBeGreaterThan(0)
    for (const path of bundles) {
      const code = await (await page.request.get(APP + path)).text()
      expect(code).not.toContain('127.0.0.1:8000')
      expect(code).not.toContain('localhost:8000')
      expect(code).not.toContain(SIGNING_KEY)
    }

    await signIn(page, 'operator@example.com')
    for (const path of ['/dashboard', '/dashboard/marketplace-data', '/dashboard/train', '/dashboard/predictor', '/dashboard/trends', '/dashboard/analytics']) {
      await page.goto(path)
      await expect(page.getByRole('main')).toBeVisible()
      await page.waitForTimeout(1500)
      const before = apiCalls.length
      await page.waitForTimeout(3000)
      expect(apiCalls.slice(before), `idle requests on ${path}`).toEqual([])
    }
    expect([...hosts].sort()).toEqual([API, APP].sort())
    const body = responses.join('\n')
    expect(body).not.toMatch(/hashed_password|token_version|marketpulse1/)
    expect(body).not.toContain(SIGNING_KEY)
  })

  test('CORS allows only configured origins, including on errors and preflight', async ({ request }) => {
    const allowed = await request.get(API + '/ml/status', { headers: { Origin: APP } })
    expect(allowed.status()).toBe(401)
    expect(allowed.headers()['access-control-allow-origin']).toBe(APP)
    const foreign = await request.get(API + '/health', { headers: { Origin: 'https://attacker.example' } })
    expect(foreign.headers()['access-control-allow-origin']).toBeUndefined()
    const preflight = await request.fetch(API + '/ml/predict', { method: 'OPTIONS', headers: { Origin: 'https://attacker.example', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type' } })
    expect(preflight.headers()['access-control-allow-origin']).toBeUndefined()
    const allowedPreflight = await request.fetch(API + '/ml/predict', { method: 'OPTIONS', headers: { Origin: APP, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type' } })
    expect(allowedPreflight.status()).toBe(200)
    expect(allowedPreflight.headers()['access-control-allow-origin']).toBe(APP)
  })

  test('trend charts have text alternatives and an empty state that says so', async ({ page }) => {
    await signIn(page, 'viewer@example.com', '/dashboard/trends')
    await expect(page.getByText('Select a product for like-for-like histories, or a category for explicitly grouped summaries.')).toBeVisible()
    const product = page.getByRole('combobox', { name: 'Product', exact: true })
    await expect(product.locator('option').nth(1)).toBeAttached()
    await product.selectOption({ index: 1 })
    const chart = page.getByRole('img').first()
    await expect(chart).toBeVisible()
    await expect(chart).toHaveAccessibleName(/\S/)
    await page.getByText('Observation values (accessible table)').first().click()
    const table = page.getByRole('table').first()
    await expect(table.getByRole('columnheader', { name: 'Price' })).toBeVisible()
    expect(await table.getByRole('row').count()).toBeGreaterThan(1)
  })

  test('form errors are specific and persist: registration, import and training/prediction failures', async ({ page }) => {
    await page.goto('/register')
    await page.getByLabel('Email', { exact: true }).fill('viewer@example.com')
    await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
    await page.getByLabel('Confirm password', { exact: true }).fill('marketpulse1')
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    const duplicate = page.getByRole('alert')
    await expect(duplicate).toBeVisible()
    await expect(duplicate).not.toContainText(/traceback|sqlalchemy|hashed/i)
    await page.waitForTimeout(4000)
    await expect(duplicate).toBeVisible()

    await signIn(page, 'operator@example.com', '/dashboard/marketplace-data')
    // Without a file the submit button is disabled rather than erroring.
    await expect(page.getByRole('button', { name: 'Import file', exact: true })).toBeDisabled()
    await page.getByLabel('CSV or JSON file').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{not json') })
    await page.getByRole('button', { name: 'Import file', exact: true }).click()
    const importError = page.getByRole('alert').filter({ hasText: /json|file|invalid|parse/i })
    await expect(importError).toBeVisible()
    await page.waitForTimeout(4000)
    await expect(importError).toBeVisible()

    await page.goto('/dashboard/train')
    await page.route('**/ml/train', (route) => route.fulfill({ status: 409, json: { detail: 'A training run is already in progress. Wait for it to finish.' } }))
    await page.getByRole('button', { name: 'Train Model', exact: true }).click()
    await expect(page.getByRole('alert').filter({ hasText: 'already in progress' })).toBeVisible()

    await page.goto('/dashboard/predictor')
    await page.route('**/ml/predict', (route) => route.fulfill({ status: 422, json: { detail: [{ loc: ['body', 'product_key'], msg: 'Field required', type: 'missing' }] } }))
    await page.getByLabel('Product / accessory', { exact: true }).selectOption({ index: 1 })
    await page.getByRole('button', { name: 'Make Prediction', exact: true }).click()
    await expect(page.getByRole('alert').filter({ hasText: 'product_key: Field required' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Prediction results' })).toHaveCount(0)
  })
})
