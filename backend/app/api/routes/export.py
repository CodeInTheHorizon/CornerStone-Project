import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.marketplace_snapshot import MarketplaceSnapshot
from app.models.prediction import Prediction
from app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])

SNAPSHOT_COLUMNS = [
    "id", "product_name", "platform", "category", "selling_price", "original_price",
    "discount_percent", "rating", "review_count", "currency", "source_type", "observed_at",
]

PREDICTION_COLUMNS = [
    "id", "product", "recommended_platform", "formula_version", "created_at",
]


def _stream_csv(rows, columns):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([getattr(row, col, None) for col in columns])
    buf.seek(0)
    return buf


@router.get("/observations")
def export_observations(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = Query(default=1000, le=10000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(MarketplaceSnapshot).order_by(MarketplaceSnapshot.observed_at.desc()).limit(limit)
    if platform:
        stmt = stmt.where(MarketplaceSnapshot.platform == platform)
    if category:
        stmt = stmt.where(MarketplaceSnapshot.category == category)
    if source_type:
        stmt = stmt.where(MarketplaceSnapshot.source_type == source_type)
    rows = list(db.scalars(stmt))
    buf = _stream_csv(rows, SNAPSHOT_COLUMNS)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=observations.csv"},
    )


@router.get("/predictions")
def export_predictions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list(db.scalars(
        select(Prediction)
        .where(Prediction.user_id == user.id)
        .order_by(Prediction.created_at.desc())
        .limit(1000)
    ))
    buf = _stream_csv(rows, PREDICTION_COLUMNS)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )
