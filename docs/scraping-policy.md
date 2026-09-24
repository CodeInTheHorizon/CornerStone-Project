# Scraping Policy — MarketPulse AI

Last reviewed: 2026-09-24

## Principles

1. **Use official APIs where available.** Scraping public pages is a fallback, not the default.
2. **Respect robots.txt.** Paths disallowed by a site's robots.txt are not scraped.
3. **No anti-bot bypasses.** CAPTCHAs, WAFs, and authentication walls are not circumvented.
4. **Minimal request volume.** Only what a search query needs; no crawling of entire catalogs.
5. **Rate limiting.** Per-platform rate limits are enforced. HTTP 429 responses trigger cooldowns.
6. **Transparent status.** Each platform's collection method, availability, and blockers are reported via `GET /data/status`.

## Per-platform policy

### Amazon (amazon.in)

| Method | Status | Notes |
|---|---|---|
| PA-API 5.0 | Deprecated | Amazon retired this endpoint; disabled in registry. |
| DataForSEO Merchant API | Default (paid) | Third-party API that aggregates Amazon product data. Requires `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` + `AMAZON_LIVE_ENABLED=true`. |
| Public search page parsing | Opt-in | Parses `amazon.in/s?k=<query>`. Gated behind `AMAZON_WEB_ENABLED=true`. Amazon's Conditions of Use restrict automated access; the operator must confirm this use is permitted. Rotates user agents, respects rate limits, backs off on 429/503. |

### Flipkart

| Method | Status | Notes |
|---|---|---|
| Affiliate API 1.0 | Default | Official documented API. Requires `FLIPKART_AFFILIATE_ID` + `FLIPKART_AFFILIATE_TOKEN` + `FLIPKART_DATA_USE_APPROVED=true`. Flipkart's terms restrict use to promotion; cross-platform analytics requires explicit approval from Flipkart. |

### Croma

| Method | Status | Notes |
|---|---|---|
| Third-party provider | Available when configured | Requires `CROMA_PROVIDER_ENABLED=true` + `CROMA_PROVIDER_BASE_URL` + `CROMA_PROVIDER_API_KEY`. |
| Web scraping | Fallback | Croma's WAF (Akamai) blocks most automated requests. The scraper attempts parsing when reachable but does not bypass the WAF. |

### Alibaba (alibaba.com)

| Method | Status | Notes |
|---|---|---|
| Third-party provider | Available when configured | Requires `ALIBABA_PROVIDER_ENABLED=true` + `ALIBABA_PROVIDER_BASE_URL` + `ALIBABA_PROVIDER_API_KEY`. |
| Web scraping | Fallback with caveat | `robots.txt` disallows `/trade/` (search). The scraper can parse search results when accessible but the operator should note this path is disallowed by robots rules. Allowed paths (`/product-detail/`, `/catalog/`) are used for detail fetches. |

## Data handling

- Scraped data is stored as `MarketplaceSnapshot` rows with source provenance (`live`, `imported`, `demo`).
- Images are proxied through `/images/proxy` to avoid hotlink-blocking; originals are cached locally.
- No personal data is collected from marketplace pages beyond publicly listed product information.
- Data retention: configurable; default is indefinite for price history analytics.

## Request patterns

- Search results only — no full-catalog crawls.
- User-agent identifies as a browser (not a bot identifier) for web scraping paths.
- Exponential backoff on failures (1s base, 3 attempts max).
- Per-platform cooldowns on rate limiting (300s default for Amazon, provider-specified for Flipkart).
- Proxy support via environment variables for each platform.
