"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/ready", summary="Deployment readiness check")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Render must not route traffic to an instance with an unreachable DB."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable.") from None
    return {"status": "ready", "database": "connected"}


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Report API liveness and database reachability.

    Returns 200 even when the database is unreachable, with the failure
    reflected in the `database` field, so a platform health probe can
    distinguish "process down" from "dependency degraded".
    """
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except SQLAlchemyError:
        database_status = "unavailable"

    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database=database_status,
        timestamp=datetime.now(timezone.utc),
    )
