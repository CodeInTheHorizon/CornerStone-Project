import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { installNetworkDiagnostics, isWebKitNavigationCancelReport } from './diagnostics'

installNetworkDiagnostics()

const API = 'http://127.0.0.1:8184'
const routes = ['/', '/register', '/login', '/dashboard', '/dashboard/marketplace-data', '/dashboard/train', '/dashboard/predictor', '/dashboard/trends', '/dashboard/analytics']
const viewports = [[1440,900], [1280,800], [768,1024], [1024,768], [390,844], [360,800]]

async function login(page: Page, role = 'operator', destination = '/dashboard') {
  await page.goto(destination)
  await expect(page.getByRole('heading', { name: 'Welcome back', exact: true })).toBeVisible()
  await page.getByLabel('Email', { exact: true }).fill(`${role}@example.com`)
  await page.getByLabel('Password', { exact: true }).fill('marketpulse1')
  await page.getByLabel('Password', { exact: true }).press('Enter')
  await expect(page).toHaveURL(new RegExp(destination.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'))
  await expect(page.getByRole('main')).toBeVisible()
}
async function token(page: Page) {
  return (await page.evaluate(() => localStorage.getItem('marketpulse-token')))!
}
async function backend(page: Page, path: string, method = 'GET', data?: object) {
  return page.request.fetch(API + path, { method, headers: { Authorization: 'Bearer ' + await token(page) }, data })
}
async function settle(page: Page, path: string) {
  await expect(page.getByRole('main')).toBeVisible()
  // The isolated DB is seeded with DEMO data and journeys add records, so the exact count varies:
  // require the loaded Stored Records card to show a positive whole number, not "Unavailable".
  if (path === '/dashboard') await expect(page.getByRole('main')).toContainText(/Stored Records\s*[1-9]\d*(?!\d)/)
  if (path.endsWith('marketplace-data')) await expect(page.getByText('Latest stored records')).toBeVisible()
  if (path.endsWith('/train')) {
    await expect(page.getByText('Loading dataset and model status…')).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Model quality', exact: true })).toBeVisible()
  }
  if (path.endsWith('/predictor')) {
    await expect(page.getByLabel('Product / accessory', { exact: true })).toBeVisible()
    await expect(page.getByText('Loading history')).toHaveCount(0)
  }
  if (path.endsWith('/trends') || path.endsWith('/analytics')) {
    // The select sits inside its <label>; getByLabel would match the option text too.
    const product = page.getByRole('combobox', { name: 'Product', exact: true })
    await expect(product.locator('option').nth(1)).toBeAttached()
    await product.selectOption({ index: 1 })
    await expect(page.getByText('Calculating stored history')).toHaveCount(0)
    if (path.endsWith('/trends')) await expect(page.getByRole('img').first()).toBeVisible()
  }
}
async function noOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }))
  expect(sizes.page).toBeLessThanOrEqual(sizes.viewport + 1)
}
async function selectProduct(page: Page) {
  const select = page.getByLabel('Product / accessory', { exact: true })
  await expect(select).toBeVisible()
  await select.selectOption({ index: 1 })
}

for (const [width, height] of viewports) for (const theme of ['light','dark'] as const) {
  test(`matrix ${width}x${height} ${theme}`, async ({ page }, testInfo) => {
    test.setTimeout(240_000)
    await page.setViewportSize({ width, height })
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    const errors: string[] = []
    const badResponses: string[] = []
    // Every route below is reached by a navigation (login or goto), so WebKit's cancel reports can occur.
    page.on('pageerror', error => { if (!isWebKitNavigationCancelReport(error)) errors.push(error.message) })
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    page.on('response', response => { if (response.status() >= 400) badResponses.push(response.url() + ':' + response.status()) })
    const findings: object[] = []
    for (const path of routes) {
      if (path === '/dashboard') await login(page)
      else await page.goto(path)
      await settle(page, path)
      await noOverflow(page)
      if (width === 1440 || width === 360) {
        const audit = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']).analyze()
        findings.push({ path, violations: audit.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })) })
      }
      if (width < 1024 && path.startsWith('/dashboard')) {
        const open = page.getByRole('button', { name: 'Open navigation', exact: true })
        await open.focus(); await page.keyboard.press('Enter')
        const dialog = page.getByRole('dialog', { name: 'Dashboard navigation' })
        await expect(dialog).toBeVisible()
        for (let i = 0; i < 12; i++) {
          await page.keyboard.press('Tab')
          expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true)
        }
        await page.keyboard.press('Escape')
        await expect(dialog).toHaveCount(0)
        await expect(open).toBeFocused()
      }
    }
    await testInfo.attach('accessibility', { body: JSON.stringify(findings, null, 2), contentType: 'application/json' })
    await testInfo.attach('accessibility-tree', { body: await page.locator('body').ariaSnapshot(), contentType: 'text/plain' })
    if (width === 360 || width === 1440) await page.screenshot({ path: testInfo.outputPath(`analytics-${theme}.png`), fullPage: true })
    expect(errors).toEqual([])
    expect(badResponses).toEqual([])
    expect(findings.filter((f: any) => f.violations.length)).toEqual([])
  })
}

for (const role of ['viewer', 'analyst', 'operator']) {
  test(`${role} complete journey, permissions and logout`, async ({ page }) => {
    await login(page, role)
    await page.goto('/dashboard/marketplace-data')
    await expect(page.getByRole('button', { name: 'Import file', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Load demo dataset', exact: true })).toBeEnabled({ enabled: role === 'operator' })
    if (role === 'operator') {
      const demo = page.waitForResponse(r => r.url().endsWith('/data/demo/load'))
      await page.getByRole('button', { name: 'Load demo dataset', exact: true }).click()
      expect((await demo).status()).toBe(200)
      await page.getByLabel('CSV or JSON file').setInputFiles({ name:'history.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify([{platform:'amazon',product_name:'Isolated E2E accessory',price:100,collection_timestamp:'2026-09-01T00:00:00Z'}])) })
      const imported = page.waitForResponse(r => r.url().endsWith('/data/import'))
      await page.getByRole('button', { name:'Import file', exact:true }).click()
      expect((await imported).status()).toBe(200)
      const collected = await backend(page, '/data/collect','POST',{platform:'flipkart',keyword:'earbuds'})
      expect(collected.status()).toBe(501)
    } else {
      expect((await backend(page, '/data/demo/load','POST')).status()).toBe(403)
      expect((await backend(page, '/data/collect','POST',{platform:'flipkart',keyword:'earbuds'})).status()).toBe(403)
    }
    await page.goto('/dashboard/train')
    await settle(page, '/dashboard/train')
    const build = page.getByRole('button', { name:'Build Dataset',exact:true })
    const train = page.getByRole('button', { name:'Train Model',exact:true })
    if (role === 'viewer') {
      await expect(build).toBeDisabled(); await expect(train).toBeDisabled()
      expect((await backend(page,'/ml/dataset/build','POST',{})).status()).toBe(403)
    } else {
      await expect(build).toBeEnabled()
      // DEMO is preselected; clicking it would deselect it and build from every source type.
      await expect(page.getByRole('group',{name:'Source types',exact:true}).first().getByRole('button',{name:'DEMO',exact:true})).toHaveAttribute('aria-pressed','true')
      const built = page.waitForResponse(r => r.url().endsWith('/ml/dataset/build'))
      await build.click(); expect((await built).status()).toBe(200)
      await expect(build).toBeEnabled()
      if (role === 'operator') {
        await page.getByRole('button',{name:'xgboost',exact:true}).click()
        const trained = page.waitForResponse(r=>r.url().endsWith('/ml/train'),{timeout:90_000})
        await train.click(); expect((await trained).status()).toBe(200)
        await expect(train).toBeEnabled({timeout:90_000})
      } else {
        await expect(train).toBeDisabled()
        expect((await backend(page,'/ml/train','POST',{source_types:['demo']})).status()).toBe(403)
      }
    }
    await page.goto('/dashboard/predictor')
    await selectProduct(page)
    const predict=page.getByRole('button',{name:'Make Prediction',exact:true})
    if (role==='viewer') await expect(predict).toBeDisabled()
    else {
      const result=page.waitForResponse(r=>r.url().endsWith('/ml/predict'))
      await predict.click();expect((await result).status()).toBe(200)
      await expect(page.getByRole('region',{name:'Prediction results'})).toBeVisible()
      await page.getByRole('button',{name:/View result #/}).first().click()
      await expect(page.getByRole('region',{name:'Prediction results'})).toBeVisible()
    }
    for (const path of ['/dashboard/trends','/dashboard/analytics']) {
      await page.goto(path);await settle(page,path);await noOverflow(page)
    }
    const oldToken=await token(page)
    await page.getByRole('button',{name:'Logout',exact:true}).click()
    await expect(page).toHaveURL(/\/login$/)
    expect((await page.request.get(API+'/auth/me',{headers:{Authorization:'Bearer '+oldToken}})).status()).toBe(401)
    await page.goto('/dashboard/predictor');await expect(page).toHaveURL(/\/login$/)
  })
}

test('normal 403 stays signed in; network and HTTP failures stay visible', async ({page}) => {
  await login(page,'analyst')
  for (const status of [403,404,413,422,429,500,502,503]) {
    await page.route('**/ml/prediction-options?*',route=>route.fulfill({status,json:{detail:`Deliberate ${status}: `+'Long error context '.repeat(16)}}))
    await page.goto('/dashboard/predictor')
    await expect(page.getByRole('alert').filter({hasText:`Deliberate ${status}`})).toBeVisible()
    await expect(page).toHaveURL(/predictor$/)
    await noOverflow(page)
    await page.unroute('**/ml/prediction-options?*')
  }
  await page.route('**/ml/prediction-options?*',route=>route.abort('connectionrefused'))
  await page.reload()
  await expect(page.getByRole('alert').filter({hasText:'Could not reach the API'})).toBeVisible()
  await page.unroute('**/ml/prediction-options?*')
  await page.route('**/ml/prediction-options?*',async route=>{await new Promise(resolve=>setTimeout(resolve,500));await route.continue()})
  await page.reload();await expect(page.getByLabel('Product / accessory',{exact:true})).toBeVisible()
  await page.unroute('**/ml/prediction-options?*')
  await page.route('**/ml/prediction-options?*',()=>new Promise(()=>{}))
  await page.reload()
  await expect(page.getByRole('alert').filter({hasText:'timed out'})).toBeVisible({timeout:35_000})
})

test('registration validation, keyboard focus, mobile navigation and theme', async ({page}) => {
  await page.setViewportSize({width:390,height:844})
  await page.goto('/')
  await page.getByRole('button',{name:'Open menu',exact:true}).focus()
  await page.keyboard.press('Space');await expect(page.getByRole('button',{name:'Close menu',exact:true})).toBeVisible()
  await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Open menu',exact:true})).toBeFocused()
  await page.goto('/register')
  await page.getByRole('button',{name:'Create account',exact:true}).press('Enter')
  await expect(page.getByText('Please enter your email address.')).toBeVisible()
  await page.getByLabel('Email',{exact:true}).fill('invalid')
  await page.getByLabel('Password',{exact:true}).fill('short')
  await page.getByLabel('Confirm password',{exact:true}).fill('different')
  await page.getByRole('button',{name:'Create account',exact:true}).press('Enter')
  await expect(page.getByText(/Enter a valid email address/)).toBeVisible()
  await expect(page.getByText('Passwords do not match.')).toBeVisible()
  const email=page.getByLabel('Email',{exact:true});await email.focus()
  const style=await email.evaluate(el=>({outline:getComputedStyle(el).outlineStyle,outlineWidth:getComputedStyle(el).outlineWidth}))
  expect(style.outline).not.toBe('none')
  expect(parseFloat(style.outlineWidth)).toBeGreaterThanOrEqual(2)
  await page.getByRole('button',{name:/Switch to .* theme/}).press('Enter')
  await noOverflow(page)
})

test('active role change, disable, revocation and expired tokens redirect safely', async ({page}) => {
  const admin=await page.request.post(API+'/auth/login',{data:{email:'administrator@example.com',password:'marketpulse1'}})
  const adminHeaders={Authorization:'Bearer '+(await admin.json()).access_token}
  for (const action of ['role','status','revoke-sessions','expired']) {
    const email=`session-${action}-${Date.now()}@example.com`
    const account=await page.request.post(API+'/auth/register',{data:{email,password:'marketpulse1'}})
    const registered=await account.json()
    await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill('marketpulse1')
    // Wait for the dashboard's own requests: a 401 arriving before reload signs out in memory, and reload then drops the message.
    const dashboardLoaded=Promise.all(['/analytics/summary','/ml/status'].map(path=>page.waitForResponse(r=>new URL(r.url()).pathname===path)))
    await page.getByRole('button',{name:'Sign in',exact:true}).click()
    await expect(page).toHaveURL(/dashboard$/)
    await dashboardLoaded
    if (action==='expired') {
      const {createHmac}=await import('node:crypto')
      const encode=(v:object)=>Buffer.from(JSON.stringify(v)).toString('base64url')
      const message=encode({alg:'HS256',typ:'JWT'})+'.'+encode({sub:String(registered.user.id),iat:1,exp:2,type:'access',token_version:0})
      const expired=message+'.'+createHmac('sha256','phase14-isolated-test-signing-key-never-deploy').update(message).digest('base64url')
      await page.evaluate(value=>localStorage.setItem('marketpulse-token',value),expired)
    } else {
      const response=await page.request.fetch(`${API}/admin/users/${registered.user.id}/${action}`,{method:action==='revoke-sessions'?'POST':'PATCH',headers:adminHeaders,data:action==='role'?{role:'analyst'}:action==='status'?{is_active:false}:undefined})
      expect(response.ok()).toBe(true)
    }
    await page.reload();await expect(page).toHaveURL(/login$/)
    await expect(page.getByRole('alert')).toContainText(/session/i)
  }
})
