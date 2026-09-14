"""Serialized account management and audit events; no request bodies in logs."""
import logging
from fastapi import HTTPException
from sqlalchemy import select, text, update
from app.models import User
from app.auth.permissions import Role

logger = logging.getLogger(__name__)

def lock_accounts(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(130013)"))
    else:
        # Acquire SQLite's writer lock before checking the active-admin invariant.
        db.execute(text("UPDATE users SET token_version = token_version WHERE id = (SELECT min(id) FROM users)"))
    db.expire_all()

def change_account(db, actor_id, target_id, *, role=None, active=None, revoke=False):
    lock_accounts(db)
    actor = db.get(User, actor_id)
    if actor is None or not actor.is_active or actor.role != Role.ADMINISTRATOR:
        raise HTTPException(403, detail="You do not have permission to perform this action.")
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(404, detail="User not found.")
    removing_admin = target.is_active and target.role == Role.ADMINISTRATOR and (
        active is False or (role is not None and role != Role.ADMINISTRATOR))
    if removing_admin:
        other = db.scalar(select(User.id).where(User.role == Role.ADMINISTRATOR, User.is_active.is_(True), User.id != target_id).limit(1))
        if other is None:
            raise HTTPException(409, detail="The last active administrator cannot be disabled or demoted.")
    changes = {}
    if role is not None and role != target.role:
        changes["role"] = role
    if active is not None and active != target.is_active:
        changes["is_active"] = active
    if changes or revoke:
        db.execute(update(User).where(User.id == target_id).values(**changes, token_version=User.token_version + 1))
        db.commit()
        if "role" in changes:
            logger.info("Role changed actor_id=%s user_id=%s role=%s", actor_id, target_id, role)
        if "is_active" in changes:
            logger.info("Account %s actor_id=%s user_id=%s", "reactivated" if active else "disabled", actor_id, target_id)
        logger.info("Sessions revoked actor_id=%s user_id=%s", actor_id, target_id)
    else:
        db.commit()
    return db.get(User, target_id)

def bootstrap_admin(db, email):
    """Explicit local operator command, only when no active admin exists."""
    lock_accounts(db)
    if db.scalar(select(User.id).where(User.role == Role.ADMINISTRATOR, User.is_active.is_(True)).limit(1)):
        raise ValueError("An active administrator already exists. Use the admin API.")
    from app.services.user_service import get_user_by_email
    target = get_user_by_email(db, email)
    if target is None or not target.is_active:
        raise ValueError("Register an active account before bootstrapping it.")
    target.role = Role.ADMINISTRATOR
    target.token_version += 1
    db.commit()
    logger.info("Administrator bootstrapped user_id=%s; sessions revoked", target.id)
