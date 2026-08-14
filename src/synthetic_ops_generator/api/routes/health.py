from fastapi import APIRouter

from synthetic_ops_generator.api.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="synthetic-ops-generator",
    )