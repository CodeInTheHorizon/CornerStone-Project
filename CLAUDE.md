@AGENTS.md

# MarketPulse AI — Real-Time Amazon Scraper Implementation Guide

Use this file to replicate the real-time Amazon web scraping feature in another Next.js (App Router) project. Follow the sections in order.

## Prerequisites

- Next.js 15+ with App Router (tested on 16.3.0)
- React 19, Tailwind v4, shadcn/ui
- pnpm (or npm/yarn)

## Step 1: Install dependency

```bash
pnpm add cheerio
```

Cheerio is the only new dependency — it parses Amazon's server-rendered HTML without a headless browser.

## Step 2: Add `amazonUrl` to your SKU type

In your types file (e.g. `lib/types.ts`), add an optional `amazonUrl` field to the `Sku` type:

```ts
export type Sku = {
  // ... existing fields ...
  amazonUrl?: string  // Amazon product page URL (e.g. "https://www.amazon.com/dp/B09B8V1LZ3")
}
```

Then seed some SKUs in your mock data with real Amazon `/dp/ASIN` URLs. SKUs without `amazonUrl` fall back to mock data — no regression.

## Step 3: Create `lib/scraper/types.ts`

Defines scraper-specific types used across the scraper module.

```ts
import type { SkuStatus } from "../types"

export type ScrapedStock = "in_stock" | "low_stock" | "out_of_stock" | "unknown"

export type ScrapedListing = {
  price: number | null
  stock: ScrapedStock
  status: SkuStatus
  raw: { title?: string; availabilityText?: string }
  scrapedAt: number
  sourceUrl: string
}

export type ScrapeErrorCode =
  | "blocked"
  | "not_found"
  | "parse_failed"
  | "network_error"

export class ScrapeError extends Error {
  code: ScrapeErrorCode
  sourceUrl: string

  constructor(code: ScrapeErrorCode, sourceUrl: string, message?: string) {
    super(message ?? `Scrape failed: ${code} for ${sourceUrl}`)
    this.name = "ScrapeError"
    this.code = code
    this.sourceUrl = sourceUrl
  }
}
```

## Step 4: Create `lib/scraper/fetcher.ts`

HTTP fetcher with mobile/desktop UA rotation, USD cookies (forces US pricing regardless of IP geo), timeout, and optional proxy support via `SCRAPER_PROXY_URL` env var.

```ts
const AMAZON_COOKIES = "i18n-prefs=USD; lc-main=en_US; sp-cdn=L5Z9:US"

const MOBILE_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  "Accept-Encoding": "gzip, deflate, br",
  "Cache-Control": "no-cache",
  Pragma: "no-cache",
  Cookie: AMAZON_COOKIES,
}

const DESKTOP_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  "Accept-Encoding": "gzip, deflate, br",
  "Cache-Control": "no-cache",
  Pragma: "no-cache",
  Cookie: AMAZON_COOKIES,
}

const FETCH_TIMEOUT_MS = 15_000

export async function fetchHtml(
  url: string,
  mode: "mobile" | "desktop" = "mobile",
): Promise<string> {
  const proxyUrl = process.env.SCRAPER_PROXY_URL
  const targetUrl = proxyUrl
    ? `${proxyUrl.replace(/\/+$/, "")}?url=${encodeURIComponent(url)}`
    : url

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)

  try {
    const res = await fetch(targetUrl, {
      headers: mode === "mobile" ? MOBILE_HEADERS : DESKTOP_HEADERS,
      signal: controller.signal,
      redirect: "follow",
    })
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`)
    return await res.text()
  } finally {
    clearTimeout(timer)
  }
}
```

**Key design decisions:**
- `i18n-prefs=USD` cookie forces USD pricing even from non-US IPs (otherwise Amazon geo-routes by IP and returns INR/EUR/etc.)
- Mobile UA is tried first because Amazon's mobile pages have more SSR-rendered price data
- `SCRAPER_PROXY_URL` env var lets you plug in ScraperAPI/Bright Data/Oxylabs for production reliability

## Step 5: Create `lib/scraper/amazon.ts`

The core Amazon product page parser with a 7-tier price extraction strategy. This is the most critical file — it went through 5 iterations of debugging to handle Amazon's quirks.

```ts
import * as cheerio from "cheerio"
import { fetchHtml } from "./fetcher"
import { ScrapeError } from "./types"
import type { ScrapedListing, ScrapedStock } from "./types"
import type { SkuStatus } from "../types"

const MAX_SANE_PRICE = 10_000

function extractPrice(text: string): number | null {
  const stripped = text
    .replace(/^[A-Z]{2,3}\s*/, "")   // "INR", "USD", "EUR" prefix
    .replace(/^[\$₹€£]/, "")          // currency symbols
    .replace(/,/g, "")                // thousand separators
    .trim()
  const val = parseFloat(stripped)
  if (isNaN(val) || val <= 0 || val > MAX_SANE_PRICE) return null
  return val
}

function parsePrice($: cheerio.CheerioAPI): number | null {
  // 1. Hidden input fields (cart/add-on logic, present in SSR HTML)
  const hiddenSelectors = [
    'input#attach-base-product-price[value]',
    'input[name="displayPrice"][value]',
    'input#priceValue[value]',
  ]
  for (const sel of hiddenSelectors) {
    const val = $(sel).attr("value")
    if (val) {
      const price = extractPrice(val)
      if (price) return price
    }
  }

  // 2. JSON-LD structured data
  for (const el of $('script[type="application/ld+json"]').toArray()) {
    try {
      const data = JSON.parse($(el).text())
      const offers = data?.offers ?? data?.Offers
      if (offers) {
        const raw = Array.isArray(offers) ? offers[0]?.price : offers?.price
        const price = parseFloat(String(raw))
        if (!isNaN(price) && price > 0) return price
      }
    } catch { /* malformed JSON-LD */ }
  }

  // 3. Meta tags
  const metaSelectors = [
    'meta[itemprop="price"]',
    'meta[property="product:price:amount"]',
    'meta[name="twitter:data1"]',
  ]
  for (const sel of metaSelectors) {
    const content = $(sel).attr("content")
    if (content) {
      const price = extractPrice(content)
      if (price) return price
    }
  }

  // 4. Composite price from whole + fraction spans (most reliable on current Amazon layouts)
  //    Amazon renders "$49.99" as two separate spans: <span class="a-price-whole">49</span>
  //    and <span class="a-price-fraction">99</span>. The .a-offscreen text often lacks decimals.
  const priceContainers = [
    "#corePrice_feature_div .a-price",
    ".a-price",
    "#price .a-price",
    "#buybox .a-price",
  ]
  for (const sel of priceContainers) {
    const container = $(sel).first()
    const whole = container.find(".a-price-whole").first().text().replace(/[^0-9]/g, "")
    const fraction = container.find(".a-price-fraction").first().text().replace(/[^0-9]/g, "")
    if (whole) {
      const combined = parseFloat(`${whole}.${fraction || "00"}`)
      if (!isNaN(combined) && combined > 0 && combined <= MAX_SANE_PRICE) return combined
    }
  }

  // 5. DOM selectors (legacy Amazon layouts)
  const domSelectors = [
    "#priceblock_ourprice", "#priceblock_dealprice", "#price_inside_buybox",
    "#newBuyBoxPrice", "#price", "#apex_offerDisplay_desktop .a-offscreen",
    "#newPitchPriceWrapper_feature_div .a-offscreen", "#mbc-price-1", ".offer-price",
  ]
  for (const sel of domSelectors) {
    const text = $(sel).first().text().trim()
    if (text) {
      const price = extractPrice(text)
      if (price) return price
    }
  }

  // 6. data-asin-price attribute
  const asinPriceEl = $("[data-asin-price]").first()
  if (asinPriceEl.length) {
    const price = extractPrice(asinPriceEl.attr("data-asin-price") ?? "")
    if (price) return price
  }

  // 7. Inline script regex — only trust decimal-format prices under $10k
  const scriptPatterns = [
    /"priceAmount"\s*:\s*(\d{1,5}\.\d{1,2})\b/,
    /"price"\s*:\s*"?\$?(\d{1,5}\.\d{2})"/,
    /"buyingPrice"\s*:\s*(\d{1,5}\.\d{1,2})\b/,
    /"our_price"\s*:\s*"(\d{1,5}\.\d{2})"/,
    /"formattedPrice"\s*:\s*"\$(\d{1,5}\.\d{2})"/,
    /"currencyPrice"\s*:\s*"\$(\d{1,5}\.\d{2})"/,
  ]
  const allScripts = $("script:not([src])").text()
  for (const pattern of scriptPatterns) {
    const match = allScripts.match(pattern)
    if (match?.[1]) {
      const price = parseFloat(match[1])
      if (!isNaN(price) && price > 0.01 && price <= MAX_SANE_PRICE) return price
    }
  }

  return null
}

function parseAvailability($: cheerio.CheerioAPI): { stock: ScrapedStock; status: SkuStatus } {
  const availText = (
    $("#availability").text() + " " +
    $("#availabilityInsideBuyBox_feature_div").text() + " " +
    $(".buying-price-availability").text()
  ).toLowerCase().trim()

  if (/currently unavailable|not available/i.test(availText)) return { stock: "out_of_stock", status: "delisted" }
  if (/temporarily out of stock/i.test(availText)) return { stock: "out_of_stock", status: "out_of_stock" }
  if (/only \d+ left/i.test(availText)) return { stock: "low_stock", status: "active" }
  if (/in stock|add to cart|buy now/i.test(availText)) return { stock: "in_stock", status: "active" }

  if ($("#add-to-cart-button, #addToCart, input[name='submit.add-to-cart']").length > 0) {
    return { stock: "in_stock", status: "active" }
  }

  return { stock: "unknown", status: "active" }
}

function detectBlock($: cheerio.CheerioAPI, url: string): void {
  if (
    $("#captchacharacters").length > 0 ||
    $("title").text().toLowerCase().includes("robot check") ||
    $("body").text().includes("Enter the characters you see below")
  ) {
    throw new ScrapeError("blocked", url, "Amazon CAPTCHA / bot detection triggered")
  }
}

export async function scrapeAmazonListing(url: string): Promise<ScrapedListing> {
  let html: string
  try {
    html = await fetchHtml(url, "mobile")
  } catch (err) {
    if (err instanceof ScrapeError) throw err
    throw new ScrapeError("network_error", url, (err as Error).message)
  }

  let $ = cheerio.load(html)
  detectBlock($, url)

  if ($("#d", "#error-page").length > 0 || $("title").text().includes("Page Not Found")) {
    throw new ScrapeError("not_found", url)
  }

  let price = parsePrice($)

  // Desktop fallback — if mobile didn't yield a price, retry with desktop UA
  if (price === null) {
    try {
      const desktopHtml = await fetchHtml(url, "desktop")
      const $d = cheerio.load(desktopHtml)
      detectBlock($d, url)
      const desktopPrice = parsePrice($d)
      if (desktopPrice !== null) { price = desktopPrice; $ = $d }
    } catch { /* desktop retry is best-effort */ }
  }

  const { stock, status } = parseAvailability($)
  const title = ($("#productTitle").text().trim() || $("#title").text().trim() || $("h1#title span").text().trim()) || undefined
  const availabilityText = $("#availability").text().trim() || undefined

  return { price, stock, status, raw: { title, availabilityText }, scrapedAt: Date.now(), sourceUrl: url }
}
```

**Pitfalls this code solves (learned the hard way):**
- Amazon splits visible prices into `a-price-whole` (49) + `a-price-fraction` (99) spans — the `.a-offscreen` text often has no decimal
- Inline script regex must require decimal format (`\d{1,5}\.\d{1,2}`) or it matches timestamps/widget IDs as garbage prices
- `MAX_SANE_PRICE = 10,000` caps all extracted prices — prevents JS artifact numbers from leaking through
- Non-US IPs get local currency (INR in India) — the `i18n-prefs=USD` cookie in fetcher.ts fixes this
- `extractPrice()` strips currency prefixes (INR, USD, $, etc.) before parsing

## Step 6: Rewrite `app/api/marketplace/sync/route.ts`

Replace the mock `marketplaceTruth()` with a real scraper that:
- Checks an in-memory TTL cache (60s) per SKU
- Falls back to mock data for SKUs without `amazonUrl`
- Uses bounded concurrency (max 3 concurrent scrapes)
- On failure, returns cached result or mock data (never crashes the whole sync)

```ts
import { NextResponse } from "next/server"
import { initialProducts } from "@/lib/mock-data"
import type { Sku, SkuStatus } from "@/lib/types"
import { scrapeAmazonListing } from "@/lib/scraper/amazon"
import { ScrapeError } from "@/lib/scraper/types"

const EXPECTED_TOKEN = process.env.MARKETPLACE_SYNC_TOKEN ?? "demo-marketplace-token"
const CACHE_TTL_MS = 60_000
const MAX_CONCURRENCY = 3

export type MarketplaceSkuSnapshot = {
  skuId: string
  marketplacePrice: number
  marketplaceStock: number
  status: SkuStatus
}

export type MarketplaceSyncResponse = {
  syncedAt: number
  source: "marketplace-live"
  skus: MarketplaceSkuSnapshot[]
}

type CacheEntry = { snapshot: MarketplaceSkuSnapshot; expiresAt: number }
const snapshotCache = new Map<string, CacheEntry>()

function mockSnapshotForSku(sku: Sku): MarketplaceSkuSnapshot {
  return {
    skuId: sku.id,
    marketplacePrice: sku.marketplacePrice,
    marketplaceStock: sku.marketplaceStock,
    status: sku.status,
  }
}

function stockToNumber(stock: "in_stock" | "low_stock" | "out_of_stock" | "unknown"): number {
  switch (stock) {
    case "in_stock": return 100
    case "low_stock": return 5
    case "out_of_stock": return 0
    case "unknown": return -1
  }
}

async function scrapeSku(sku: Sku): Promise<MarketplaceSkuSnapshot> {
  const now = Date.now()
  const cached = snapshotCache.get(sku.id)
  if (cached && cached.expiresAt > now) return cached.snapshot
  if (!sku.amazonUrl) return mockSnapshotForSku(sku)

  try {
    const listing = await scrapeAmazonListing(sku.amazonUrl)
    const snapshot: MarketplaceSkuSnapshot = {
      skuId: sku.id,
      marketplacePrice: listing.price ?? sku.marketplacePrice,
      marketplaceStock: stockToNumber(listing.stock),
      status: listing.status,
    }
    snapshotCache.set(sku.id, { snapshot, expiresAt: now + CACHE_TTL_MS })
    return snapshot
  } catch (err) {
    if (cached) return cached.snapshot
    console.error(`Scrape failed for ${sku.id}:`, err instanceof ScrapeError ? `${err.code} — ${err.message}` : err)
    return mockSnapshotForSku(sku)
  }
}

async function scrapeMarketplaceTruth(): Promise<MarketplaceSkuSnapshot[]> {
  const allSkus: Sku[] = initialProducts.flatMap((p) => p.skus)
  const results: MarketplaceSkuSnapshot[] = []
  for (let i = 0; i < allSkus.length; i += MAX_CONCURRENCY) {
    const batch = allSkus.slice(i, i + MAX_CONCURRENCY)
    const batchResults = await Promise.all(batch.map(scrapeSku))
    results.push(...batchResults)
  }
  return results
}

export async function GET(request: Request) {
  const auth = request.headers.get("authorization")
  const token = auth?.replace(/^Bearer\s+/i, "")
  if (!token || token !== EXPECTED_TOKEN) {
    return NextResponse.json({ error: "Unauthorized. Provide a valid marketplace sync token." }, { status: 401 })
  }
  const response: MarketplaceSyncResponse = {
    syncedAt: Date.now(),
    source: "marketplace-live",
    skus: await scrapeMarketplaceTruth(),
  }
  return NextResponse.json(response, { headers: { "cache-control": "no-store" } })
}
```

## Step 7: Add auto-polling to `lib/use-dashboard.ts`

Add these to your dashboard hook:

1. Import `useEffect`, `useRef`
2. Add state: `lastSyncedAt` (number | null), `autoPolling` (boolean, default true)
3. Add a `syncRef` that always points to the latest `sync` function
4. Add a `useEffect` that runs `sync("demo-marketplace-token")` every 60s when `autoPolling` is true
5. Set `lastSyncedAt = Date.now()` on successful sync
6. Return `lastSyncedAt`, `autoPolling`, `setAutoPolling` from the hook

## Step 8: Update `components/sync-bar.tsx`

Add to SyncBar:

1. A `timeAgo(ts)` helper that returns "just now", "Xs ago", "Xm ago", "Xh ago"
2. A 1-second ticking interval to keep the time-ago label live
3. An Auto/Paused toggle button (Play/Pause icons from lucide-react)
4. Props: `syncedAt: number | null`, `autoPolling: boolean`, `onToggleAutoPolling: () => void`

## Step 9: Wire it up in `components/dashboard.tsx`

Destructure `lastSyncedAt`, `autoPolling`, `setAutoPolling` from `useDashboard()` and pass them to `<SyncBar>`.

## Architecture Summary

```
Browser (60s poll)
    |
    v
GET /api/marketplace/sync  (Bearer token auth)
    |
    +-- SKU has amazonUrl? --> scrapeAmazonListing(url)
    |                              |
    |                              +-- fetchHtml(url, "mobile")
    |                              |       +-- 15s timeout, USD cookies
    |                              |
    |                              +-- cheerio.load(html)
    |                              |       +-- 7-tier price extraction
    |                              |       +-- availability parsing
    |                              |       +-- CAPTCHA detection
    |                              |
    |                              +-- price null? --> retry desktop UA
    |
    +-- No amazonUrl? --> mockSnapshotForSku(sku)
    |
    +-- Scrape failed? --> return cached or mock (never crash)
    |
    +-- In-memory TTL cache (60s per SKU)
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MARKETPLACE_SYNC_TOKEN` | `demo-marketplace-token` | Bearer token for sync API auth |
| `SCRAPER_PROXY_URL` | (none) | Optional proxy service URL (ScraperAPI, Bright Data, etc.) |

## Known Limitations

- Amazon actively blocks non-browser scraping. For production, use `SCRAPER_PROXY_URL` with a rotating proxy service, or switch to Amazon's Selling Partner API (SP-API) for ToS-compliant access.
- Prices are capped at $10,000 (`MAX_SANE_PRICE`) to filter garbage from inline JS.
- In-memory cache resets on server restart (no persistence layer).
- Cheerio only parses static HTML — some prices are rendered client-side via JS and may return null.

## Files Changed (Summary)

| File | Action | What |
|------|--------|------|
| `package.json` | Modified | Added `cheerio` dependency |
| `lib/types.ts` | Modified | Added `amazonUrl?: string` to `Sku` type |
| `lib/mock-data.ts` | Modified | Added `amazonUrl` to 2 test SKUs |
| `lib/scraper/types.ts` | New | Scraper data types + `ScrapeError` class |
| `lib/scraper/fetcher.ts` | New | HTTP fetcher with UA rotation + USD cookies |
| `lib/scraper/amazon.ts` | New | 7-tier Amazon price parser + availability + CAPTCHA detection |
| `app/api/marketplace/sync/route.ts` | Rewritten | Real scraping with cache, concurrency, fallbacks |
| `lib/use-dashboard.ts` | Modified | Added 60s auto-polling + lastSyncedAt state |
| `components/sync-bar.tsx` | Modified | Added time-ago, auto/pause toggle |
| `components/dashboard.tsx` | Modified | Wired auto-polling props to SyncBar |
