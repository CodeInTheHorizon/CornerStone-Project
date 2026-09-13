"""MarketPulse AI FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes import health
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare local storage directories and the database schema on startup."""
    # Refuse to run outside development with the shipped placeholder secret:
    # every token would be forgeable by anyone who has read this repository.
    if settings.uses_default_jwt_secret and not settings.is_development:
        raise RuntimeError(
            "JWT_SECRET_KEY is still the development default. Set a strong, "
            "random value before running outside development."
        )

    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for MarketPulse AI - marketplace data collection, "
        "dataset building, model training and marketplace opportunity prediction."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Pydantic includes raw input (including passwords) unless explicitly removed.
    errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unexpected_failure(request: Request, exc: Exception):
    # Exception text and full paths may contain user data; log only the failure class.
    logger.error("Unhandled API failure: %s %s", request.method, type(exc).__name__)
    origin = request.headers.get("origin")
    headers = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"} if origin in settings.CORS_ORIGINS else {}
    return JSONResponse(status_code=500, headers=headers, content={"detail": "The request could not be completed. Please retry; if it persists, contact the operator."})


# Allow the local Vite dev server (and any configured deployed frontend)
# to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unprefixed system endpoints.
app.include_router(health.router)
# Prefixed feature endpoints (populated from Phase 3 onward).
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["system"], summary="API root")
def root() -> dict[str, str]:
    """Minimal service descriptor."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
