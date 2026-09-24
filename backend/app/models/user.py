"""User account model.

Phase 1 defines the table only. Password hashing, registration and JWT
issuing are introduced in Phase 3.
"""

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Stores a hash only -- never a plaintext password.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role: Mapped[str] = mapped_column(String(24), default="viewer", server_default="viewer", nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    @property
    def permissions(self) -> list[str]:
        from app.auth.permissions import permissions_for
        return permissions_for(self.role)

    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r}>"
