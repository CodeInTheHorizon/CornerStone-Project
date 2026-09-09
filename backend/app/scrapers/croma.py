"""Croma adapter -- not available for public collection.

Verified 2026-09-10: both https://www.croma.com/robots.txt and the search
endpoint return HTTP 403 "Access Denied" from Akamai edge protection.

Working around an edge WAF is an anti-bot bypass, so this collector stays
inert. Croma publishes no public product API.
"""

from app.models.enums import Platform
from app.scrapers.base import UnavailableCollector


class CromaCollector(UnavailableCollector):
    def __init__(self) -> None:
        super().__init__(
            platform=Platform.CROMA,
            access_method="None available",
            reason=(
                "Croma returns HTTP 403 (Akamai 'Access Denied') to "
                "programmatic requests, including for robots.txt. Bypassing "
                "edge anti-bot protection is out of scope. No public product "
                "API is offered."
            ),
        )
