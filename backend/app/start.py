"""Render entrypoint: python -m app.start (from backend/).

One worker preserves the existing process-local training coordination.
"""

import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
        proxy_headers=False,  # Never accept spoofed X-Forwarded-For for rate limits.
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.ACCESS_LOG,
    )


if __name__ == "__main__":
    main()
