from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertListResponse, AlertRead, AlertUpdate
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=AlertRead, status_code=201)
def create_alert(
    body: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return alert_service.create_alert(db, user.id, body)


@router.get("", response_model=AlertListResponse)
def list_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alerts = alert_service.list_alerts(db, user.id)
    return AlertListResponse(alerts=alerts, total=len(alerts))


@router.get("/triggered", response_model=list[AlertRead])
def triggered_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return alert_service.get_triggered(db, user.id)


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(
    alert_id: int,
    body: AlertUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = alert_service.update_alert(db, alert_id, user.id, body)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not alert_service.delete_alert(db, alert_id, user.id):
        raise HTTPException(404, "Alert not found")
