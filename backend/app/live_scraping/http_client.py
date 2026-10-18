"""The one HTTP client every marketplace scraper goes through.

Policy enforced here, so no adapter can forget it:

* **robots.txt** is checked before every request and every redirect hop.
  robots.txt that cannot be read (5xx, network error, 401/403/429, or an HTML
  challenge page served in its place) is treated as "disallow everything".
* **Pacing**: at most one request per host per `min_interval_seconds`.
* **Retries** only for transient failures -- timeouts, connection errors and
  500/502/503/504 -- with exponential backoff and jitter.
* **Blocks are final.** A CAPTCHA, bot page, 401/403 or 429 raises
  immediately. It is never retried, and nothing here tries to look less like
  an automated client to get past one.
* **Proxy**: one operator-configured HTTP/HTTPS proxy (for example a corporate
  egress proxy). There is deliberately no proxy rotation.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import requests

from app.live_scraping.errors import (
    HttpStatusError,
    NetworkError,
    ProductNotFoundError,
    RateLimitedError,
    RobotsDisallowedError,
    SourceBlockedError,
)
from app.live_scraping.rate_limit import HostRateLimiter
from app.live_scraping.robots import MAX_ROBOTS_BYTES, RobotsRules

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 5
#: Cooldown hint when a 429 carries no usable Retry-After.
DEFAULT_RETRY_AFTER_SECONDS = 900.0

_CHARSET = re.compile(r"charset=([\w.:-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class HttpClientConfig:
    user_agent: str
    accept_language: str = "en-IN,en;q=0.9"
    #: Product token used to pick the robots.txt group. Not sent as a header.
    robots_agent: str = "MarketPulseBot"
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    max_attempts: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    min_interval_seconds: float = 5.0
    http_proxy: str | None = None
    https_proxy: str | None = None
    max_response_bytes: int = 8 * 1024 * 1024
    robots_ttl_seconds: float = 24 * 3600.0

    @classmethod
    def from_settings(cls, settings) -> "HttpClientConfig":
        return cls(
            user_agent=settings.SCRAPER_USER_AGENT,
            accept_language=settings.SCRAPER_ACCEPT_LANGUAGE,
            robots_agent=settings.SCRAPER_ROBOTS_AGENT,
            connect_timeout=settings.SCRAPER_CONNECT_TIMEOUT_SECONDS,
            read_timeout=settings.SCRAPER_READ_TIMEOUT_SECONDS,
            max_attempts=settings.SCRAPER_MAX_ATTEMPTS,
            backoff_base=settings.SCRAPER_BACKOFF_BASE_SECONDS,
            backoff_max=settings.SCRAPER_BACKOFF_MAX_SECONDS,
            min_interval_seconds=settings.SCRAPER_MIN_INTERVAL_SECONDS,
            http_proxy=settings.SCRAPER_HTTP_PROXY.get_secret_value() or None,
            https_proxy=settings.SCRAPER_HTTPS_PROXY.get_secret_value() or None,
        )


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    text: str
    content_type: str | None
    elapsed_ms: int
    #: HTTP requests made for this page, counting retries but not redirects.
    attempts: int


#: Adapter hook: return a human-readable reason when the page is a block page.
BlockDetector = Callable[[FetchedPage], str | None]


def parse_retry_after(value: str | None) -> float | None:
    """Retry-After as seconds (delta or HTTP date), capped at 24 h; None when unusable."""
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, min(seconds, 24 * 3600.0))


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class PoliteHttpClient:
    def __init__(
        self,
        config: HttpClientConfig,
        *,
        session: requests.Session | None = None,
        limiter: HostRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config
        self._session = session or requests.Session()
        self._session.headers.update({
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": config.accept_language,
            "Accept-Encoding": "gzip, deflate",
        })
        proxies = {k: v for k, v in (("http", config.http_proxy), ("https", config.https_proxy)) if v}
        if proxies:
            self._session.proxies.update(proxies)
        self._limiter = limiter or HostRateLimiter(config.min_interval_seconds, sleep=sleep, clock=clock)
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._robots: dict[str, tuple[float, RobotsRules, str | None]] = {}
        self._robots_lock = threading.Lock()

    # ------------------------------------------------------------------ public

    def get(self, url: str, *, detect_block: BlockDetector | None = None) -> FetchedPage:
        """Fetch one HTML page under the full policy. Raises a ScrapeError subclass on failure."""
        started = self._clock()
        current = url
        attempts = 0
        for _ in range(MAX_REDIRECTS + 1):
            self._ensure_allowed(current)
            response, used = self._request_with_retries(current)
            attempts += used
            if response.status_code in REDIRECT_STATUS and response.headers.get("Location"):
                response.close()
                current = urljoin(current, response.headers["Location"])
                continue
            page = self._to_page(url, current, response, attempts, started)
            return self._classify(page, response, detect_block)
        raise HttpStatusError(f"More than {MAX_REDIRECTS} redirects fetching {url}")

    def close(self) -> None:
        self._session.close()

    # ---------------------------------------------------------------- robots

    def _ensure_allowed(self, url: str) -> None:
        rules, problem = self._robots_for(url)
        if problem is not None:
            raise RobotsDisallowedError(
                f"robots.txt for {_host(url)} could not be read ({problem}); treating the site as disallowed.",
                source_level=True,
            )
        if not rules.is_allowed(url, self.config.robots_agent):
            raise RobotsDisallowedError(f"robots.txt disallows {urlsplit(url).path}")

    def _robots_for(self, url: str) -> tuple[RobotsRules, str | None]:
        origin = _origin(url)
        now = self._clock()
        with self._robots_lock:
            cached = self._robots.get(origin)
            if cached and now - cached[0] < self.config.robots_ttl_seconds:
                return cached[1], cached[2]
        rules, problem = self._fetch_robots(origin)
        with self._robots_lock:
            self._robots[origin] = (self._clock(), rules, problem)
        return rules, problem

    def _fetch_robots(self, origin: str) -> tuple[RobotsRules, str | None]:
        robots_url = f"{origin}/robots.txt"
        self._limiter.wait(_host(robots_url))
        try:
            response = self._session.get(
                robots_url,
                timeout=(self.config.connect_timeout, self.config.read_timeout),
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            return RobotsRules.disallow_all(), f"network error: {type(exc).__name__}"

        status = response.status_code
        body = response.content[:MAX_ROBOTS_BYTES].decode("utf-8", errors="replace")
        content_type = (response.headers.get("Content-Type") or "").lower()
        if status in (401, 403, 429):
            return RobotsRules.disallow_all(), f"HTTP {status}"
        if status >= 500:
            return RobotsRules.disallow_all(), f"HTTP {status}"
        if 400 <= status < 500:
            # RFC 9309 2.3.1.3: robots.txt "unavailable" -- no restrictions apply.
            return RobotsRules.allow_all(), None
        if "html" in content_type or body.lstrip().lower().startswith(("<!doctype", "<html")):
            # A challenge page served in place of robots.txt is a block, not a policy.
            return RobotsRules.disallow_all(), "an HTML page was served instead of robots.txt"
        return RobotsRules.parse(body), None

    # ------------------------------------------------------------ requests

    def _request_with_retries(self, url: str) -> tuple[requests.Response, int]:
        host = _host(url)
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            self._limiter.wait(host)
            try:
                response = self._session.get(
                    url,
                    timeout=(self.config.connect_timeout, self.config.read_timeout),
                    allow_redirects=False,
                    stream=True,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                logger.info("GET %s attempt %d/%d failed: %s", url, attempt, self.config.max_attempts, type(exc).__name__)
            else:
                if response.status_code not in RETRYABLE_STATUS or attempt == self.config.max_attempts:
                    return response, attempt
                last_error = None
                # A 503 may be a bot page; the caller inspects the final response,
                # but an intermediate one is only retried if it is not.
                if self._looks_blocked_quickly(response):
                    return response, attempt
                response.close()
                logger.info("GET %s attempt %d/%d returned %d", url, attempt, self.config.max_attempts, response.status_code)
            if attempt < self.config.max_attempts:
                self._backoff(host, attempt)

        raise NetworkError(
            f"Request failed after {self.config.max_attempts} attempts ({type(last_error).__name__})."
        )

    def _backoff(self, host: str, attempt: int) -> None:
        delay = min(self.config.backoff_max, self.config.backoff_base * 2 ** (attempt - 1))
        delay += self._rng.uniform(0, self.config.backoff_base)
        self._limiter.defer(host, delay)

    @staticmethod
    def _looks_blocked_quickly(response: requests.Response) -> bool:
        # Retry-After on a 503 is a throttle signal: stop rather than hammer.
        return bool(response.headers.get("Retry-After"))

    def _to_page(self, requested: str, final: str, response: requests.Response, attempts: int, started: float) -> FetchedPage:
        content_type = response.headers.get("Content-Type")
        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > self.config.max_response_bytes:
                    raise HttpStatusError(
                        f"Response exceeded {self.config.max_response_bytes} bytes.", http_status=response.status_code
                    )
                chunks.append(chunk)
        except requests.RequestException as exc:
            raise NetworkError(f"Connection dropped while reading the page ({type(exc).__name__}).") from None
        finally:
            response.close()

        match = _CHARSET.search(content_type or "")
        encoding = match.group(1) if match else "utf-8"
        try:
            text = b"".join(chunks).decode(encoding, errors="replace")
        except LookupError:
            text = b"".join(chunks).decode("utf-8", errors="replace")

        return FetchedPage(
            requested_url=requested,
            final_url=final,
            status_code=response.status_code,
            text=text,
            content_type=content_type,
            elapsed_ms=int((self._clock() - started) * 1000),
            attempts=attempts,
        )

    def _classify(self, page: FetchedPage, response: requests.Response, detect_block: BlockDetector | None) -> FetchedPage:
        status = page.status_code
        reason = detect_block(page) if detect_block else None
        if reason:
            raise SourceBlockedError(reason, http_status=status)
        if status == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            self._limiter.defer(_host(page.final_url), retry_after or DEFAULT_RETRY_AFTER_SECONDS)
            raise RateLimitedError(
                "HTTP 429: the marketplace asked for fewer requests.",
                retry_after_seconds=retry_after or DEFAULT_RETRY_AFTER_SECONDS,
            )
        if status in (401, 403):
            raise SourceBlockedError(f"HTTP {status}: access denied to ordinary requests.", http_status=status)
        if status in (404, 410):
            raise ProductNotFoundError(f"HTTP {status}: product page not found.", http_status=status)
        if status == 503 and response.headers.get("Retry-After"):
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            raise RateLimitedError("HTTP 503 with Retry-After: the marketplace is shedding load.",
                                   retry_after_seconds=retry_after, http_status=503)
        if status >= 400:
            raise HttpStatusError(f"HTTP {status}.", http_status=status)
        return page
