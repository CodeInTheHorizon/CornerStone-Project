"""Image proxy and cache.

Downloads product images from source platforms once, caches them locally, and
serves them from our domain so hotlink-blocking or expiring CDN URLs don't
break the UI.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

CACHE_DIR = Path(os.environ.get("IMAGE_CACHE_DIR", "image_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
DOWNLOAD_TIMEOUT = 10.0

ALLOWED_DOMAINS = {
    "images-amazon.com",
    "m.media-amazon.com",
    "rukminim1.flixcart.com",
    "rukminim2.flixcart.com",
    "media-ik.croma.com",
    "sc04.alicdn.com",
    "s.alicdn.com",
    "i.ebayimg.com",
}

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}

_PLACEHOLDER_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <rect width="200" height="200" fill="#f0f0f0"/>
  <text x="100" y="90" text-anchor="middle" font-family="system-ui" font-size="14" fill="#999">No image</text>
  <text x="100" y="115" text-anchor="middle" font-family="system-ui" font-size="12" fill="#bbb">available</text>
</svg>'''


def _is_allowed_domain(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        return any(host.endswith(d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _extension(url: str, content_type: str | None = None) -> str:
    if content_type:
        for ext, ct in CONTENT_TYPES.items():
            if ct == content_type:
                return ext
    for ext in CONTENT_TYPES:
        if ext in url.lower():
            return ext
    return ".jpg"


@router.get("/proxy")
async def proxy_image(
    url: str = Query(description="Source image URL to proxy"),
) -> Response:
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    if not _is_allowed_domain(url):
        raise HTTPException(status_code=403, detail="Image domain not allowed")

    url_hash = _url_hash(url)
    cached_files = list(CACHE_DIR.glob(f"{url_hash}.*"))
    if cached_files:
        cached = cached_files[0]
        ct = CONTENT_TYPES.get(cached.suffix, "image/jpeg")
        return FileResponse(cached, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})

    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; MarketPulseBot/1.0)",
                "Accept": "image/*",
            })
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Source returned {resp.status_code}")

            if len(resp.content) > MAX_IMAGE_SIZE:
                raise HTTPException(status_code=502, detail="Image too large")

            content_type = resp.headers.get("content-type", "").split(";")[0].strip()
            ext = _extension(url, content_type)
            ct = CONTENT_TYPES.get(ext, "image/jpeg")

            cache_path = CACHE_DIR / f"{url_hash}{ext}"
            cache_path.write_bytes(resp.content)

            return Response(
                content=resp.content,
                media_type=ct,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Image proxy failed for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail="Could not fetch image") from exc


@router.get("/placeholder")
async def placeholder_image() -> Response:
    return Response(
        content=_PLACEHOLDER_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=604800"},
    )
