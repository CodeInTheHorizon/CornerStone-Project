"""Read-only, authenticated analytics; no collection or model execution."""

from datetime import date

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.models.enums import Platform, SourceType
from app.schemas.analytics import AnalyticsFilters
from app.services import analytics_service as service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def filters(
    product: str | None = Query(default=None, min_length=1, max_length=512),
    product_key: str | None = Query(default=None, min_length=1, max_length=900),
    platform: Platform | None = None, category: str | None = Query(default=None, min_length=1, max_length=120),
    source_type: SourceType | None = None, start_date: date | None = None, end_date: date | None = None,
) -> AnalyticsFilters:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, detail={"status": "invalid_date_range", "reason": "start_date must be on or before end_date."})
    return AnalyticsFilters(product, product_key, platform, category, source_type, start_date, end_date)


def call(function, *args):
    try:
        return function(*args)
    except service.AnalyticsError as exc:
        logger.warning("Analytics request rejected: %s", exc.detail["status"])
        raise HTTPException(422, detail=exc.detail) from None


@router.get("/trends")
def trends(
    query: AnalyticsFilters = Depends(filters), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> dict:
    return call(service.trends, db, query, limit, offset)


@router.get("/platform-comparison")
def comparison(query: AnalyticsFilters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return call(service.comparison, db, user.id, query)


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return service.summary(db, user.id)


@router.get("/options")
def options(
    query: AnalyticsFilters = Depends(filters), q: str = Query(default="", max_length=120),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> dict:
    return call(service.options, db, query, q, limit, offset)
