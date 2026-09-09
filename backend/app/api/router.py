"""Aggregate router for feature endpoints.

Feature routers are registered here as their phases land, keeping main.py free
of per-feature wiring. /health is mounted separately at the application root so
platform health probes always have a stable, unprefixed path.
"""

from fastapi import APIRouter

from app.api.routes import auth, data

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(data.router)
