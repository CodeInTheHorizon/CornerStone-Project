"""MarketPulse AI FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
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
