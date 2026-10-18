"""Live product-page collection for MarketPulse.

Layers, each replaceable on its own:

    http_client  -- requests.Session, robots.txt, pacing, retries, proxy
    adapters/    -- one parser per marketplace (HTML -> raw strings)
    normalize    -- raw strings -> validated `ProductObservation` (Pydantic)
    base         -- `ObservationSource`, the seam an API/provider plugs into
    registry     -- which source serves which marketplace
    service      -- scheduling, append-only storage, failure handling
    __main__     -- CLI: python -m app.live_scraping --help

Never bypasses CAPTCHAs, sign-in walls or bot detection, and never stores a
value it did not read from the page.
"""
