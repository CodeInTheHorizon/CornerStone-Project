"""Failure types for live product-page collection.

Every failure carries an `outcome` that is written to `scrape_attempts`, and
`source_level` says whether the failure means the whole marketplace is
unavailable (a bot wall, a throttle, JavaScript-only pages) or only this one
product (a 404, a page the robots rules exclude).

A source-level failure stops the run for that marketplace. The collector never
retries its way past a block: it records the block and waits for the cooldown.
"""

from __future__ import annotations

from enum import Enum


class ScrapeOutcome(str, Enum):
    """Result of one product-page attempt, stored in scrape_attempts.outcome."""

    SUCCESS = "success"
    #: CAPTCHA, bot-detection page, access denied or a sign-in wall.
    BLOCKED = "blocked"
    #: robots.txt forbids the URL, or robots.txt itself could not be read.
    ROBOTS_DISALLOWED = "robots_disallowed"
    #: HTTP 429. The marketplace asked us to slow down.
    RATE_LIMITED = "rate_limited"
    #: The product page no longer exists.
    NOT_FOUND = "not_found"
    #: The server HTML is an app shell; the data is rendered by JavaScript.
    JS_RENDERED = "js_rendered"
    #: The page loaded but the parser could not find the product in it.
    PARSE_FAILED = "parse_failed"
    #: An HTTP error that is neither a block nor a missing page.
    HTTP_ERROR = "http_error"
    #: Timeout, DNS failure, connection reset, proxy failure.
    NETWORK_ERROR = "network_error"
    #: The operator has not enabled this marketplace, or no adapter exists yet.
    DISABLED = "disabled"


class ScrapeError(Exception):
    """Base class. Messages must never contain proxy credentials or page bodies."""

    outcome: ScrapeOutcome = ScrapeOutcome.HTTP_ERROR
    source_level: bool = False

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class SourceBlockedError(ScrapeError):
    """The marketplace refused ordinary access. Never bypassed; the source is marked unavailable."""

    outcome = ScrapeOutcome.BLOCKED
    source_level = True


class RobotsDisallowedError(ScrapeError):
    """robots.txt forbids the fetch.

    `source_level` is True when robots.txt itself was unreachable or refused,
    which RFC 9309 treats as "disallow everything" -- that is a property of the
    site, not of one product.
    """

    outcome = ScrapeOutcome.ROBOTS_DISALLOWED

    def __init__(self, message: str, *, source_level: bool = False, http_status: int | None = None) -> None:
        super().__init__(message, http_status=http_status)
        self.source_level = source_level


class RateLimitedError(ScrapeError):
    outcome = ScrapeOutcome.RATE_LIMITED
    source_level = True

    def __init__(self, message: str, *, retry_after_seconds: float | None = None, http_status: int | None = 429) -> None:
        super().__init__(message, http_status=http_status)
        self.retry_after_seconds = retry_after_seconds


class ProductNotFoundError(ScrapeError):
    outcome = ScrapeOutcome.NOT_FOUND


class JavaScriptRenderedError(ScrapeError):
    """The data is not in the server HTML. Executing the page's JavaScript is out of scope."""

    outcome = ScrapeOutcome.JS_RENDERED
    source_level = True


class ParseFailedError(ScrapeError):
    outcome = ScrapeOutcome.PARSE_FAILED


class HttpStatusError(ScrapeError):
    outcome = ScrapeOutcome.HTTP_ERROR


class NetworkError(ScrapeError):
    outcome = ScrapeOutcome.NETWORK_ERROR


class SourceDisabledError(ScrapeError):
    outcome = ScrapeOutcome.DISABLED
    source_level = True
