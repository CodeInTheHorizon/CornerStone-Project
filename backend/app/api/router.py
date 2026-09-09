"""Aggregate router for prefixed feature endpoints.

Feature routers (auth, data, ml, analytics) are registered here as their
phases land, keeping main.py free of per-feature wiring. It is empty in
Phase 1 -- /health is mounted at the application root instead, so that
platform health probes can use a stable, unprefixed path.
"""

from fastapi import APIRouter

api_router = APIRouter()
