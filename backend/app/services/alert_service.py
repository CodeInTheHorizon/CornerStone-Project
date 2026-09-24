from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.alert import PriceAlert
from app.models.marketplace_snapshot import MarketplaceSnapshot
from app.schemas.alert import AlertCreate, AlertUpdate


def create_alert(db: Session, user_id: int, data: AlertCreate) -> PriceAlert:
    alert = PriceAlert(
        user_id=user_id,
        product_name=data.product_name,
        platform=data.platform,
        condition=data.condition,
        threshold=data.threshold,
        currency=data.currency,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(db: Session, user_id: int) -> list[PriceAlert]:
    return list(db.scalars(select(PriceAlert).where(PriceAlert.user_id == user_id).order_by(PriceAlert.created_at.desc())))


def get_triggered(db: Session, user_id: int) -> list[PriceAlert]:
    return list(db.scalars(
        select(PriceAlert)
        .where(PriceAlert.user_id == user_id, PriceAlert.triggered_at.isnot(None))
        .order_by(PriceAlert.triggered_at.desc())
        .limit(50)
    ))


def update_alert(db: Session, alert_id: int, user_id: int, data: AlertUpdate) -> PriceAlert | None:
    alert = db.scalar(select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id))
    if not alert:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return alert


def delete_alert(db: Session, alert_id: int, user_id: int) -> bool:
    alert = db.scalar(select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id))
    if not alert:
        return False
    db.delete(alert)
    db.commit()
    return True


def check_alerts(db: Session) -> int:
    active_alerts = list(db.scalars(select(PriceAlert).where(PriceAlert.active == True)))
    triggered_count = 0
    for alert in active_alerts:
        latest = db.scalar(
            select(MarketplaceSnapshot.selling_price)
            .where(
                func.lower(MarketplaceSnapshot.product_name).contains(alert.product_name.lower()),
                func.lower(MarketplaceSnapshot.platform) == alert.platform.lower(),
                MarketplaceSnapshot.selling_price.isnot(None),
            )
            .order_by(MarketplaceSnapshot.observed_at.desc())
            .limit(1)
        )
        if latest is None:
            continue
        triggered = False
        if alert.condition == "below" and latest <= alert.threshold:
            triggered = True
        elif alert.condition == "above" and latest >= alert.threshold:
            triggered = True
        if triggered:
            alert.triggered_at = datetime.now(timezone.utc)
            alert.triggered_value = latest
            triggered_count += 1
    if triggered_count:
        db.commit()
    return triggered_count
