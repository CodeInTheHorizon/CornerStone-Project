"""Response schemas for the health endpoint."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness/readiness payload returned by GET /health."""

    status: str = Field(description="'ok' when the API is serving requests.")
    app: str
    version: str
    environment: str
    database: str = Field(
        description="'connected' when a test query succeeded, otherwise 'unavailable'."
    )
    timestamp: datetime
