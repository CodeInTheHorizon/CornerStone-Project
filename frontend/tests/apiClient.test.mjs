import { after, afterEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

// Vite resolves the same aliases/environment transforms as the app. No browser,
// new framework dependency or real API call is needed for these failure paths.
const server = await createServer({ server: { middlewareMode: true, hmr: false } })
const { apiRequest, ApiRequestError } = await server.ssrLoadModule('/src/services/apiClient.ts')
const { importDataset } = await server.ssrLoadModule('/src/services/dataService.ts')
const originalFetch = globalThis.fetch
const originalWindow = globalThis.window
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
afterEach(() => { globalThis.fetch = originalFetch; globalThis.window = originalWindow })
after(async () => { await server.close() })

test('offline backend gives an actionable error', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline') }
  await assert.rejects(apiRequest('/health'), (error) => error instanceof ApiRequestError && /Could not reach/.test(error.message))
})

test('timeout terminates waiting and warns against duplicate server mutations', async () => {
  globalThis.fetch = async (_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted'))))
  await assert.rejects(apiRequest('/ml/train', { method: 'POST', timeoutMs: 10 }), /timed out.*Server work may still finish/)
})

test('timeout also covers a stalled response body', async () => {
  globalThis.fetch = async (_url, init) => ({ ok: true, status: 200, json: async () => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted')))) })
  await assert.rejects(apiRequest('/health', { timeoutMs: 10 }), /timed out/)
})

test('401 emits session rejection only for authenticated calls', async () => {
  globalThis.window = new EventTarget()
  const rejected = []
  window.addEventListener('marketpulse:unauthorized', (event) => rejected.push(event.detail.token))
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Not authenticated.' }), { status: 401 })
  await assert.rejects(apiRequest('/ml/predictions', { token: 'fixture-token' }), (error) => error.isUnauthorized)
  await assert.rejects(apiRequest('/auth/login', { method: 'POST' }))
  assert.deepEqual(rejected, ['fixture-token'])
})

test('403, 404, 422, 500 and unavailable upstream errors remain readable', async () => {
  for (const status of [403, 404, 422, 500, 501, 502]) {
    globalThis.fetch = async () => new Response('proxy error', { status })
    await assert.rejects(apiRequest('/example'), (error) => error.status === status && error.message.length > 15)
  }
})

test('structured errors retain model failure context and field validation', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { reason: 'Missing model.', platform_results: [] } }), { status: 422 })
  await assert.rejects(apiRequest('/ml/predict'), (error) => error.message === 'Missing model.' && Array.isArray(error.detail.platform_results))
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ loc: ['body', 'password'], msg: 'Too short' }] }), { status: 422 })
  await assert.rejects(apiRequest('/auth/register'), /password: Too short/)
})

test('multipart import uses shared request handling without a JSON boundary header', async () => {
  globalThis.fetch = async (_url, init) => {
    assert.equal(init.headers.has('Content-Type'), false)
    assert.equal(init.headers.get('Authorization'), 'Bearer fixture-token')
    assert.ok(init.body instanceof FormData)
    return new Response(JSON.stringify({ source_type: 'imported', stored: 1 }))
  }
  const result = await importDataset('fixture-token', new File(['[]'], 'fixture.json'))
  assert.equal(result.source_type, 'imported')
})

test('unreadable success payload cannot become a null page model', async () => {
  globalThis.fetch = async () => new Response('not-json')
  await assert.rejects(apiRequest('/analytics/summary'), /unreadable response/)
  globalThis.fetch = async () => new Response(null, { status: 204 })
  assert.equal(await apiRequest('/example'), undefined)
  await sleep(1)
})
