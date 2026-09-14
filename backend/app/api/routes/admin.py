"""Minimal administrator-only account APIs; predictions remain owner-only."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.auth.permissions import Permission, Role
from app.database import get_db
from app.models import User
from app.schemas.auth import UserRead
from app.services.account_service import change_account

router = APIRouter(prefix="/admin", tags=["admin"])
admin_user = require_permission(Permission.MANAGE_USERS)

class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role

class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: StrictBool

@router.get("/users", response_model=list[UserRead])
def users(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
          actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id).limit(limit).offset(offset)).all()

@router.patch("/users/{user_id}/role", response_model=UserRead)
def role(user_id: int, payload: RoleChange, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    return change_account(db, actor.id, user_id, role=payload.role)

@router.patch("/users/{user_id}/status", response_model=UserRead)
def status(user_id: int, payload: StatusChange, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    return change_account(db, actor.id, user_id, active=payload.is_active)

@router.post("/users/{user_id}/revoke-sessions", response_model=UserRead)
def revoke(user_id: int, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    return change_account(db, actor.id, user_id, revoke=True)
