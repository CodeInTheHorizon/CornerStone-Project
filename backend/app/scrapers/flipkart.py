"""Flipkart adapter -- not available for public collection.

Verified 2026-09-10: https://www.flipkart.com/robots.txt does not serve a
robots file at all; it returns a Google reCAPTCHA Enterprise interstitial
("Are you a human?"). Every unauthenticated programmatic request meets the
same challenge.

Collecting from Flipkart would therefore require solving or evading a CAPTCHA,
which this project does not do. Flipkart's Affiliate API, which would have
been the permitted route, is closed to new registrations.

If an official data feed becomes available, replace this stub with a real
collector; nothing outside this module needs to change.
"""

from app.models.enums import Platform
from app.scrapers.base import UnavailableCollector


class FlipkartCollector(UnavailableCollector):
    def __init__(self) -> None:
        super().__init__(
            platform=Platform.FLIPKART,
            access_method="None available",
            reason=(
                "Flipkart serves a reCAPTCHA challenge to programmatic "
                "requests (its robots.txt itself returns the challenge page). "
                "Collecting would require evading a CAPTCHA, which this "
                "project does not do. The Affiliate API is closed to new "
                "registrations."
            ),
        )
