"""Authenticated Phase 7 prediction and user-scoped history endpoints."""

from app.auth.permissions import Permission
from app.auth.rate_limits import operation


import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.prediction import PredictRequest, PredictionHistory, PredictionResponse
from app.services import prediction_service as service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["prediction"])


def call(function, *args):
    try:
        return function(*args)
    except service.PredictionError as exc:
        logger.warning("Prediction request rejected: %s", exc.detail["status"])
        raise HTTPException(status_code=exc.http_status, detail=exc.detail) from None


@router.get("/prediction-options")
def prediction_options(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
) -> dict:
    return call(service.options, q, limit, offset)


@router.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictRequest, db: Session = Depends(get_db), user: User = Depends(operation(Permission.PREDICT, "predict"))):
    return call(service.predict, db, user.id, payload)


@router.get("/predictions", response_model=PredictionHistory)
def predictions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.history(db, user.id, limit, offset)


@router.get("/predictions/{prediction_id}", response_model=PredictionResponse)
def prediction_detail(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return call(service.detail, db, user.id, prediction_id)
