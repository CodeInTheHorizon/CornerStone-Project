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
    "ssl-images-amazon.com",
    "media-amazon.com",
    "m.media-amazon.com",
    "rukminim1.flixcart.com",
    "rukminim2.flixcart.com",
    "static-assets-web.flixcart.com",
    "media-ik.croma.com",
    "media.croma.com",
    "croma.com",
    "sc04.alicdn.com",
    "s.alicdn.com",
    "img.alicdn.com",
    "aliimg.com",
    "alibaba.com",
    "i.ebayimg.com",
    "images.meesho.com",
    "meesho.com",
    "unsplash.com",
    "images.unsplash.com",
    "dummyjson.com",
    "cdn.dummyjson.com",
    "raw.githubusercontent.com",
}

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}

_PLACEHOLDER_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#F1F5F9"/>
      <stop offset="100%" stop-color="#E2E8F0"/>
    </linearGradient>
  </defs>
  <rect width="400" height="300" rx="12" fill="url(#bg)"/>
  <circle cx="200" cy="130" r="50" fill="#CBD5E1" opacity="0.6"/>
  <path d="M185 110 h30 a5 5 0 0 1 5 5 v30 a5 5 0 0 1 -5 5 h-30 a5 5 0 0 1 -5 -5 v-30 a5 5 0 0 1 5 -5 z" fill="#64748B" opacity="0.8"/>
  <circle cx="200" cy="122" r="7" fill="#FFFFFF"/>
  <text x="200" y="210" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="14" font-weight="600" fill="#64748B">MarketPulse AI</text>
  <text x="200" y="230" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="12" fill="#94A3B8">Product Catalog</text>
</svg>'''


def _is_allowed_domain(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        # Allow any known CDN or any subdomain of allowed domains
        return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False
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
    if not url or not url.startswith("http") or "grey-pixel.gif" in url:
        return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")

    url_hash = _url_hash(url)
    cached_files = list(CACHE_DIR.glob(f"{url_hash}.*"))
    if cached_files:
        cached = cached_files[0]
        ct = CONTENT_TYPES.get(cached.suffix, "image/jpeg")
        return FileResponse(cached, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})

    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            })
            if resp.status_code != 200:
                logger.warning("Source returned %s for %s, serving placeholder", resp.status_code, url)
                return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")

            if len(resp.content) > MAX_IMAGE_SIZE:
                return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")

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
    except Exception as exc:
        logger.warning("Image proxy failed for %s: %s; serving placeholder", url, exc)
        return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")


@router.get("/placeholder")
async def placeholder_image() -> Response:
    return Response(
        content=_PLACEHOLDER_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=604800"},
    )
