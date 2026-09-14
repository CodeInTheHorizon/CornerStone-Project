"""Only for isolated tests; public registration deliberately stays viewer."""
from app.database import SessionLocal
from app.models import User

def grant_role(user_id, role="operator"):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.role = role
        db.commit()
