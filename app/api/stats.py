from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project
from ..schemas.stats import HealthResponse, OverviewResponse, PeriodStats
from ..services import stats_service
from .deps import get_current_project, get_db

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=OverviewResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    data = await stats_service.get_overview(db, project.id)
    return OverviewResponse(
        today=PeriodStats(**data["today"]),
        week=PeriodStats(**data["week"]),
        month=PeriodStats(**data["month"]),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")
