"""Alibaba adapter -- not available under the site's robots rules.

Verified 2026-09-10: https://www.alibaba.com/robots.txt contains
`Disallow: /trade/`, and product search lives at /trade/search. The search
endpoint does respond to requests, but responding is not permission -- the
robots rules disallow it, so this collector does not use it.

The paths robots does allow (/catalog/, /product-detail/, /showroom/) are
browse and detail pages, not keyword search, so they cannot satisfy the
keyword-driven collection this system needs.

Alibaba's Open Platform API would be the permitted route and requires an
approved developer app key.
"""

from app.models.enums import Platform
from app.scrapers.base import UnavailableCollector


class AlibabaCollector(UnavailableCollector):
    def __init__(self) -> None:
        super().__init__(
            platform=Platform.ALIBABA,
            access_method="None available",
            reason=(
                "Alibaba's robots.txt disallows /trade/, which is where "
                "keyword search lives. The allowed paths (/catalog/, "
                "/product-detail/) do not support keyword search. The Open "
                "Platform API requires an approved developer app key."
            ),
            requires_credentials=True,
        )
