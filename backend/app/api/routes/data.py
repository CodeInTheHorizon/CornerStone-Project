"""Marketplace data endpoints: collection, import, demo loading and status.

All of these require authentication: collection performs outbound requests on
the operator's credentials, and the stored data is the project's own dataset.
"""

from app.auth.permissions import Permission
from app.auth.rate_limits import operation


import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import MarketplaceSnapshot, User
from app.models.enums import SourceType, Platform
from app.schemas.data import (
    CollectRequest,
    CollectResponse,
    DemoDatasetInfo,
    IngestSummary,
    PlatformStatus,
    SnapshotListResponse,
    SnapshotRead,
    StatusResponse,
)
from app.scrapers import (
    CollectorRateLimitedError,
    CollectorRequestError,
    CollectorUnavailableError,
    UnknownPlatformError,
)
from app.services import collection_service, demo_service, import_service
from app.services.ingest import IngestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["marketplace-data"])


def _summary(result: IngestResult) -> IngestSummary:
    return IngestSummary(
        status="success" if result.stored else "empty",
        source_type=SourceType(result.source_type),
        batch_id=result.batch_id,
        timestamp=result.timestamp,
        stored=result.stored,
        rejected=result.rejected,
        duplicates=result.duplicates,
        platforms=result.platforms,
        warnings=result.warnings,
        rejected_rows=result.rejected_rows,
    )


@router.post(
    "/collect",
    response_model=CollectResponse,
    summary="Collect fresh listings from a marketplace",
)
def collect(
    payload: CollectRequest,
    db: Session = Depends(get_db),
    _: User = Depends(operation(Permission.COLLECT, "collect")),
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
    except CollectorRateLimitedError as exc:
        # 429: pass the provider's throttle through instead of hammering it.
        retry_after = max(1, int(exc.retry_after_seconds or 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(retry_after)},
        ) from None
    except CollectorRequestError as exc:
        # 502: we are the gateway and the upstream source failed or refused
        # our credentials. The message says which; secrets are never included.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from None

    return CollectResponse(
        status="success" if result.items_collected else "empty",
        platform=result.platform,
        keyword=result.keyword,
        source_type=SourceType(result.source_type),
        provider=result.provider,
        items_received=result.items_received,
        items_collected=result.items_collected,
        items_rejected=result.items_rejected,
        duplicates_skipped=result.duplicates_skipped,
        collection_run_id=result.collection_run_id,
        collection_timestamp=result.collection_timestamp,
        warnings=result.warnings,
    )


@router.post(
    "/import",
    response_model=IngestSummary,
    summary="Import a CSV or JSON marketplace dataset",
)
def import_dataset(
    file: UploadFile = File(description="CSV or JSON file of marketplace records."),
    db: Session = Depends(get_db),
    _: User = Depends(operation(Permission.IMPORT, "import")),
) -> IngestSummary:
    """Store an operator-supplied dataset as IMPORTED records.

    Imported rows go through the same validation, normalization and
    deduplication as live collection. They are tagged IMPORTED, never LIVE:
    this system did not observe them and cannot attest to how they were taken.
    """
    content = file.file.read(import_service.MAX_IMPORT_BYTES + 1)
    if len(content) > import_service.MAX_IMPORT_BYTES:
        raise HTTPException(413, detail="Uploaded file exceeds the 5 MiB limit.")

    try:
        result = import_service.import_dataset(
            db, content=content, filename=file.filename or ""
        )
    except import_service.ImportError_ as exc:
        logger.warning("Dataset import rejected")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    return _summary(result)


@router.post(
    "/demo/load",
    response_model=IngestSummary,
    summary="Load the bundled synthetic demo dataset",
)
def load_demo(
    replace: bool = Query(
        default=True,
        description="Clear previously loaded demo rows first. Live and imported data is never touched.",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(operation(Permission.DEMO, "demo")),
) -> IngestSummary:
    """Load the development fixture as DEMO records.

    The dataset is synthetic: invented brands, generated prices and ratings.
    It exists so later phases are testable while most marketplaces cannot be
    collected from. Every row is tagged DEMO and must never be shown as live.
    """
    try:
        result = demo_service.load_demo_dataset(db, replace=replace)
    except demo_service.DemoDatasetMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None

    return _summary(result)


@router.get(
    "/latest",
    response_model=SnapshotListResponse,
    summary="Most recently collected marketplace records",
)
def latest(
    platform: Platform | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    source_type: SourceType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SnapshotListResponse:
    rows = collection_service.latest_snapshots(
        db,
        platform=platform,
        keyword=keyword,
        category=category,
        source_type=source_type.value if source_type else None,
        limit=limit,
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
    platform: Platform | None = Query(default=None),
    product: str | None = Query(default=None, max_length=512),
    category: str | None = Query(default=None, max_length=120),
    source_type: SourceType | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SnapshotListResponse:
    start = (start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)) if start else None
    end = (end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end.astimezone(timezone.utc)) if end else None
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
        source_type=source_type.value if source_type else None,
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
    summary="Ingestion mode and data availability per platform",
)
def collector_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StatusResponse:
    counts = collection_service.snapshot_counts(db)
    by_source = collection_service.source_types_by_platform(db)

    platforms: dict[str, PlatformStatus] = {}
    last_overall: datetime | None = None

    for name, state in collection_service.platform_statuses(db).items():
        last = collection_service.last_collection_at(db, name)
        if last and (last_overall is None or last > last_overall):
            last_overall = last
        fetches = collection_service.fetch_history(db, name)

        platforms[name] = PlatformStatus(
            available=state.available,
            state=state.state,
            ingestion_mode=state.ingestion_mode,
            access_method=state.access_method,
            provider=state.provider,
            reason=state.reason,
            requires_credentials=state.requires_credentials,
            # Variable names only; values are never exposed.
            required_configuration=list(state.required_configuration),
            last_collection=last,
            stored_records=counts.get(name, 0),
            source_types_available=by_source.get(name, []),
            live_records=fetches.live_records,
            last_live_observation=fetches.last_live_observation,
            last_successful_fetch=fetches.last_successful_fetch,
            last_failed_fetch=fetches.last_failed_fetch,
            last_failure_state=fetches.last_failure_outcome,
            last_failure_reason=fetches.last_failure_reason,
            retry_after=fetches.retry_after,
        )

    source_totals = {
        row[0]: row[1]
        for row in db.execute(
            select(
                MarketplaceSnapshot.source_type, func.count(MarketplaceSnapshot.id)
            ).group_by(MarketplaceSnapshot.source_type)
        ).all()
    }

    try:
        described = demo_service.describe()
        demo = DemoDatasetInfo(
            available=True,
            record_count=described["record_count"],
            platforms=described["platforms"],
            categories=described["categories"],
            loaded_records=demo_service.demo_row_count(db),
        )
    except demo_service.DemoDatasetMissingError as exc:
        demo = DemoDatasetInfo(available=False, reason=str(exc))

    return StatusResponse(
        platforms=platforms,
        total_snapshots=sum(counts.values()),
        last_collection=last_overall,
        records_by_source_type=source_totals,
        demo_dataset=demo,
    )
