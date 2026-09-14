"""Alibaba adapter -- not available under the site's robots rules.

Verified 2026-09-10: https://www.alibaba.com/robots.txt contains
`Disallow: /trade/`, and product search lives at /trade/search. The search
endpoint does respond to requests, but responding is not permission -- the
robots rules disallow it, so this collector does not use it. The paths robots
allows (/catalog/, /product-detail/, /showroom/) are browse and detail pages,
not keyword search.

Rechecked 2026-09-14: the Alibaba.com Open API is a seller/ERP API for
synchronising a paid seller's *own* products and orders. It offers no
marketplace-wide keyword search, so an app key would not unblock this
collector and none is requested.
"""

from app.models.enums import Platform
from app.scrapers.base import UnavailableCollector


class AlibabaCollector(UnavailableCollector):
    def __init__(self) -> None:
        super().__init__(
            platform=Platform.ALIBABA,
            access_method="None available",
            reason=(
                "Alibaba's robots.txt disallows /trade/, which is where keyword "
                "search lives, and the allowed paths do not support keyword search. "
                "The Alibaba.com Open API only manages a seller's own products and "
                "orders; it has no marketplace search, so no credential would help."
            ),
        )
