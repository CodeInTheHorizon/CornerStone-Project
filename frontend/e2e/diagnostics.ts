/**
 * Network diagnostics for every E2E test: failed requests (with the browser's failure
 * reason) and HTTP responses >= 400. Only method, URL and status/reason are recorded:
 * never headers (Authorization), request/response bodies, JWTs or secrets.
 * The log is attached to the test result as `network-diagnostics`.
 */
import { test, type Page } from '@playwright/test'

export interface NetworkEvent {
  /** `after-response`: the browser reported a failure for a request that already has a response
   *  (Chromium does this for body-less 204 responses). Informational, not a network failure. */
  kind: 'requestfailed' | 'after-response' | 'http-error'
  method: string
  url: string
  detail: string
}

const logs = new WeakMap<Page, NetworkEvent[]>()

/** Strips any query-string token-like parameter; URLs in this app carry no credentials. */
function safeUrl(raw: string) {
  const url = new URL(raw)
  for (const key of [...url.searchParams.keys()]) if (/token|secret|password|key/i.test(key)) url.searchParams.set(key, 'redacted')
  return url.toString()
}

/** Real problems only: failed requests that never received a response, and HTTP errors. */
export function networkEvents(page: Page): NetworkEvent[] {
  return (logs.get(page) ?? []).filter((event) => event.kind !== 'after-response')
}

/**
 * Playwright's WebKit reports the engine's log line for a fetch cancelled by a page navigation
 * ("Fetch API cannot load <url> due to access control checks.") as a page error. Measured on
 * this app: 13 such reports during goto/reload loops while in-page `unhandledrejection` and
 * `error` listeners recorded 0, so no application exception exists. Callers must only apply
 * this after the test itself navigated; real CORS failures are covered by the CORS test and by
 * Chromium/Firefox, which do not produce this report.
 */
export function isWebKitNavigationCancelReport(error: Error) {
  return /^Fetch API cannot load http/.test(`${error.name} ${error.message}`) && / due to access control checks\.$/.test(error.message)
}

export function installNetworkDiagnostics() {
  test.beforeEach(({ page }) => {
    const events: NetworkEvent[] = []
    logs.set(page, events)
    page.on('requestfailed', async (request) => {
      const response = await request.response().catch(() => null)
      events.push({ kind: response ? 'after-response' : 'requestfailed', method: request.method(), url: safeUrl(request.url()), detail: `${request.failure()?.errorText ?? 'unknown'}${response ? ` (response ${response.status()})` : ''}` })
    })
    page.on('response', (response) => {
      if (response.status() >= 400) events.push({ kind: 'http-error', method: response.request().method(), url: safeUrl(response.url()), detail: String(response.status()) })
    })
  })
  test.afterEach(async ({ page }, testInfo) => {
    const events = logs.get(page) ?? []
    if (events.length) await testInfo.attach('network-diagnostics', { body: JSON.stringify(events, null, 2), contentType: 'application/json' })
  })
}
