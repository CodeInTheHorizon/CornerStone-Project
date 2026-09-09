"""Marketplace data collection endpoints.

All of these require authentication: collection performs outbound requests on
the operator's credentials, and the stored data is the project's own dataset.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.data import (
    CollectRequest,
    CollectResponse,
    PlatformStatus,
    SnapshotListResponse,
    SnapshotRead,
    StatusResponse,
)
from app.scrapers import (
    CollectorRequestError,
    CollectorUnavailableError,
    UnknownPlatformError,
    all_statuses,
)
from app.services import collection_service

router = APIRouter(prefix="/data", tags=["marketplace-data"])


@router.post(
    "/collect",
    response_model=CollectResponse,
    summary="Collect fresh listings from a marketplace",
)
def collect(
    payload: CollectRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CollectResponse:
    try:
        result = collection_service.run_collection(
            db,
            platform=payload.platform,
            keyword=payload.keyword,
            category=payload.category,
            max_items=payload.max_items,
        )
    except UnknownPlatformError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None
    except CollectorUnavailableError as exc:
        # 501: the request is valid, this platform is simply not supported.
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        ) from None
    except CollectorRequestError as exc:
        # 502: we are the gateway and the upstream source failed.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from None

    return CollectResponse(
        status="success" if result.items_collected else "empty",
        platform=result.platform,
        keyword=result.keyword,
        items_collected=result.items_collected,
        items_rejected=result.items_rejected,
        duplicates_skipped=result.duplicates_skipped,
        collection_run_id=result.collection_run_id,
        collection_timestamp=result.collection_timestamp,
        warnings=result.warnings,
    )


@router.get(
    "/latest",
    response_model=SnapshotListResponse,
    summary="Most recently collected marketplace records",
)
def latest(
    platform: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SnapshotListResponse:
    rows = collection_service.latest_snapshots(
        db, platform=platform, keyword=keyword, category=category, limit=limit
    )
    return SnapshotListResponse(
        count=len(rows), items=[SnapshotRead.model_validate(row) for row in rows]
    )


@router.get(
    "/history",
    response_model=SnapshotListResponse,
    summary="Stored snapshots over a time window, oldest first",
)
def history(
    platform: str | None = Query(default=None),
    product: str | None = Query(default=None),
    category: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SnapshotListResponse:
    if start and end and start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'start' must be before 'end'.",
        )

    rows = collection_service.snapshot_history(
        db,
        platform=platform,
        product=product,
        category=category,
        start=start,
        end=end,
        limit=limit,
    )
    return SnapshotListResponse(
        count=len(rows), items=[SnapshotRead.model_validate(row) for row in rows]
    )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Collector availability per platform",
)
def collector_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StatusResponse:
    counts = collection_service.snapshot_counts(db)
    platforms: dict[str, PlatformStatus] = {}
    last_overall: datetime | None = None

    for name, state in all_statuses().items():
        last = collection_service.last_collection_at(db, name)
        if last and (last_overall is None or last > last_overall):
            last_overall = last

        platforms[name] = PlatformStatus(
            available=state.available,
            access_method=state.access_method,
            reason=state.reason,
            requires_credentials=state.requires_credentials,
            last_collection=last,
            stored_snapshots=counts.get(name, 0),
        )

    return StatusResponse(
        platforms=platforms,
        total_snapshots=sum(counts.values()),
        last_collection=last_overall,
    )
