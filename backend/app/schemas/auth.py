"""Request/response schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Long enough to be meaningful, short enough to stay inside bcrypt's 72-byte
# limit even for multi-byte characters.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 64


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="At least 8 characters, including a letter and a number.",
    )
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(char.isalpha() for char in value):
            raise ValueError("Password must contain at least one letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number.")
        return value

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Public view of a user. Deliberately omits the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds.")
    user: UserRead
