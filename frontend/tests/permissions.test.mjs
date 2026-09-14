import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true, hmr: false } })
const { can, PERMISSIONS, ROLE_PERMISSIONS, roleLabel } = await server.ssrLoadModule('/src/auth/permissions.ts')
const { normalizeUser } = await server.ssrLoadModule('/src/auth/normalizeUser.ts')
const { PermissionGate } = await server.ssrLoadModule('/src/components/PermissionGate.tsx')
const { AuthContext } = await server.ssrLoadModule('/src/auth/authContext.ts')
const { ThemeContext } = await server.ssrLoadModule('/src/theme/themeContext.ts')
const { Sidebar } = await server.ssrLoadModule('/src/components/dashboard/Sidebar.tsx')
const { DashboardPage } = await server.ssrLoadModule('/src/pages/DashboardPage.tsx')
const React = await import('react')
const { renderToStaticMarkup } = await import('react-dom/server')
const { MemoryRouter } = await import('react-router-dom')
after(async () => { await server.close() })

/** Exactly what a backend before Phase 13 returned: active, but no role or permissions. */
const PRE_PHASE_13_USER = { id: 7, email: 'legacy@example.com', full_name: null, is_active: true, created_at: '2026-09-01T00:00:00Z' }

const auth = (value) => ({ user: null, token: 'token', status: 'authenticated', sessionError: null, login: async () => {}, register: async () => {}, logout: async () => {}, ...value })
function renderGate(value, permission) {
  return renderToStaticMarkup(React.createElement(AuthContext.Provider, { value: auth(value) },
    React.createElement(PermissionGate, { permission }, React.createElement('button', null, 'Action'))))
}
function renderInApp(value, component) {
  const theme = { preference: 'light', theme: 'light', setPreference() {}, toggle() {} }
  return renderToStaticMarkup(React.createElement(MemoryRouter, null,
    React.createElement(ThemeContext.Provider, { value: theme },
      React.createElement(AuthContext.Provider, { value: auth(value) }, React.createElement(component)))))
}
const account = (role, permissions = ROLE_PERMISSIONS[role]) => ({ id: 1, email: `${role}@example.com`, role, permissions, is_active: true })

// --- Valid roles: exactly the backend mapping ------------------------------

for (const role of ['viewer', 'analyst', 'operator', 'administrator']) {
  test(`valid ${role} gets exactly its mapped permissions`, () => {
    const user = account(role)
    for (const permission of PERMISSIONS) {
      const allowed = ROLE_PERMISSIONS[role].includes(permission)
      assert.equal(can(user, permission), allowed, `${role} ${permission}`)
      const html = renderGate({ user }, permission)
      assert.equal(html.includes('disabled=""'), !allowed)
      assert.equal(html.includes('You do not have permission'), !allowed)
    }
  })
}

test('role mapping matches backend/app/auth/permissions.py', () => {
  const source = readFileSync(new URL('../../backend/app/auth/permissions.py', import.meta.url), 'utf8')
  const enumValues = Object.fromEntries([...source.matchAll(/^\s+(\w+) = "([\w:]+)"$/gm)].map(([, name, value]) => [name, value]))
  const members = (text) => [...text.matchAll(/Permission\.(\w+)/g)].map(([, name]) => enumValues[name])
  const viewer = members(source.match(/_VIEWER = frozenset\(\{([^}]*)\}\)/)[1])
  const analyst = [...viewer, ...members(source.match(/_ANALYST = _VIEWER \| \{([^}]*)\}/)[1])]
  const operator = [...analyst, ...members(source.match(/_OPERATOR = _ANALYST \| \{([^}]*)\}/)[1])]
  const permissionValues = Object.values(enumValues).filter((value) => value.includes(':'))
  const sorted = (list) => [...new Set(list)].sort()
  assert.deepEqual(sorted(ROLE_PERMISSIONS.viewer), sorted(viewer))
  assert.deepEqual(sorted(ROLE_PERMISSIONS.analyst), sorted(analyst))
  assert.deepEqual(sorted(ROLE_PERMISSIONS.operator), sorted(operator))
  assert.deepEqual(sorted(ROLE_PERMISSIONS.administrator), sorted(permissionValues))
  assert.deepEqual(sorted(PERMISSIONS), sorted(permissionValues))
})

// --- Missing, unknown or malformed role state denies without throwing -----

for (const [label, role] of [['undefined', undefined], ['null', null], ['unknown', 'superuser'], ['empty', ''], ['non-string', 42]]) {
  test(`${label} role denies every permission`, () => {
    const user = { id: 1, email: 'x@example.com', role, permissions: [...PERMISSIONS], is_active: true }
    for (const permission of PERMISSIONS) assert.equal(can(user, permission), false)
    assert.match(renderGate({ user }, 'model:train'), /disabled=""/)
    assert.match(renderGate({ user }, 'model:train'), /Your role: unknown role/)
  })
}

test('stale pre-Phase 13 user (active, no role, no permissions) denies and does not throw', () => {
  for (const permission of PERMISSIONS) assert.equal(can(PRE_PHASE_13_USER, permission), false)
})

for (const [label, permissions] of [['missing', undefined], ['null', null], ['a string', 'model:train'], ['an object', { 'model:train': true }], ['non-string items', [1, null, {}]]]) {
  test(`permissions field ${label} denies without throwing`, () => {
    assert.equal(can({ ...account('operator'), permissions }, 'model:train'), false)
  })
}

test('missing permission mapping denies', () => {
  const operator = account('operator')
  assert.equal(can(operator, 'model:train', {}), false)
  assert.equal(can(operator, 'model:train', { viewer: ['workspace:read'] }), false)
  assert.equal(can(operator, 'model:train', { operator: undefined }), false)
  assert.equal(can(operator, 'model:train', { operator: 'model:train' }), false)
})

test('server permissions beyond the role mapping cannot unlock a control', () => {
  assert.equal(can(account('viewer', [...PERMISSIONS]), 'model:train'), false)
  assert.equal(can(account('analyst', [...PERMISSIONS]), 'users:manage'), false)
})

test('unknown permission names and non-user values deny', () => {
  assert.equal(can(account('administrator'), 'everything:allow'), false)
  for (const value of [null, undefined, 'operator', 42, [], true]) assert.equal(can(value, 'workspace:read'), false)
})

test('missing or disabled account fails closed', () => {
  assert.equal(can(null, 'model:train'), false)
  assert.equal(can({ ...account('administrator'), is_active: false }, 'model:train'), false)
  assert.equal(can({ ...account('administrator'), is_active: 'true' }, 'model:train'), false)
  assert.match(renderGate({ user: null, status: 'anonymous' }, 'model:train'), /Sign in to continue/)
})

// --- Loading auth state -----------------------------------------------------

test('loading auth state keeps actions disabled without a denial message', () => {
  const html = renderGate({ user: account('operator'), status: 'restoring' }, 'model:train')
  assert.match(html, /disabled=""/)
  assert.match(html, /Checking your permissions/)
  assert.doesNotMatch(html, /You do not have permission/)
  assert.match(renderGate({ user: null, status: 'restoring' }, 'dataset:build'), /Checking your permissions/)
})

// --- Normalization at the API boundary ---------------------------------------

test('pre-Phase 13 payload normalizes to a role-less, permission-less account', () => {
  assert.deepEqual(normalizeUser(PRE_PHASE_13_USER), { ...PRE_PHASE_13_USER, role: null, permissions: [] })
})

test('normalization keeps valid fields and drops unknown ones', () => {
  const user = normalizeUser({ id: 3, email: 'a@example.com', full_name: 'A', role: 'analyst', permissions: ['dataset:build', 'root:all', 5], is_active: true, created_at: 'x' })
  assert.equal(user.role, 'analyst')
  assert.deepEqual(user.permissions, ['dataset:build'])
  assert.equal(normalizeUser({ ...user, role: 'owner' }).role, null)
  assert.equal(normalizeUser({ ...user, is_active: 1 }).is_active, false)
})

test('payloads that are not accounts normalize to null', () => {
  for (const value of [null, undefined, 'user', [], {}, { id: '1', email: 'a@example.com' }, { id: 1, email: '' }]) {
    assert.equal(normalizeUser(value), null)
  }
})

test('role labels never throw', () => {
  assert.equal(roleLabel('operator'), 'operator')
  for (const value of [undefined, null, 'root', 3]) assert.equal(roleLabel(value), 'unknown role')
})

// --- The crashing screens ----------------------------------------------------

test('Dashboard renders for the stale pre-Phase 13 user instead of crashing', () => {
  const html = renderInApp({ user: PRE_PHASE_13_USER }, DashboardPage)
  assert.match(html, /Prepare Dataset/)
  assert.match(html, /You do not have permission/)
})

test('Dashboard renders for a normalized legacy user and for an operator', () => {
  assert.match(renderInApp({ user: normalizeUser(PRE_PHASE_13_USER) }, DashboardPage), /unknown role/)
  const operator = renderInApp({ user: account('operator') }, DashboardPage)
  assert.match(operator, /Train Model/)
})

test('Sidebar renders for the stale pre-Phase 13 user and labels the role unknown', () => {
  const html = renderInApp({ user: PRE_PHASE_13_USER }, Sidebar)
  assert.match(html, /Datasets \/ Model Status/)
  assert.match(html, /legacy@example\.com · unknown role/)
})
