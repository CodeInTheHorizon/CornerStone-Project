"""Croma adapter -- not available for public collection.

Verified 2026-09-10: both https://www.croma.com/robots.txt and the search
endpoint return HTTP 403 "Access Denied" from Akamai edge protection.
Working around an edge WAF is an anti-bot bypass, so this collector stays
inert.

Rechecked 2026-09-14: Croma publishes no public product API. Product data is
offered only to selected affiliates of third-party networks (for example
INRDeals "Super Affiliates") for promoting Croma, which neither this project
holds nor covers storing history for analytics.
"""

from app.models.enums import Platform
from app.scrapers.base import UnavailableCollector


class CromaCollector(UnavailableCollector):
    def __init__(self) -> None:
        super().__init__(
            platform=Platform.CROMA,
            access_method="None available",
            reason=(
                "Croma returns HTTP 403 (Akamai 'Access Denied') to programmatic "
                "requests, including for robots.txt, and bypassing edge anti-bot "
                "protection is out of scope. Croma offers no public product API; "
                "affiliate-network product feeds are for promotion only."
            ),
        )
