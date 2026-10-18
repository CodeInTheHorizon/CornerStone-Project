"""Aggregate router for feature endpoints.

Feature routers are registered here as their phases land, keeping main.py free
of per-feature wiring. /health is mounted separately at the application root so
platform health probes always have a stable, unprefixed path.
"""

from fastapi import APIRouter

from app.api.routes import admin, alerts, analytics, auth, data, dataset, export, images, ml, optimization, prediction, products, profitability, scoring, search

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(data.router)
api_router.include_router(dataset.router)
api_router.include_router(ml.router)
api_router.include_router(prediction.router)
api_router.include_router(analytics.router)
api_router.include_router(alerts.router)
api_router.include_router(export.router)
api_router.include_router(search.router)
api_router.include_router(images.router)
api_router.include_router(products.router)
api_router.include_router(scoring.router)
api_router.include_router(profitability.router)
api_router.include_router(optimization.router)

api_router.include_router(admin.router)
