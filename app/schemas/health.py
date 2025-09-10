from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Service status, e.g., ok")
    name: str = Field(description="Service name")
    version: str = Field(description="Service semantic version")
    time: datetime = Field(description="Current server time in UTC")
    env: str = Field(description="Current environment")
