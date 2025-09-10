from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        name=settings.PROJECT_NAME,
        version=settings.VERSION,
        time=datetime.now(timezone.utc),
        env=settings.ENV,
    )
