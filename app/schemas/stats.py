from pydantic import BaseModel


class PeriodStats(BaseModel):
    total: int
    success: int
    failed: int


class OverviewResponse(BaseModel):
    today: PeriodStats
    week: PeriodStats
    month: PeriodStats


class HealthResponse(BaseModel):
    status: str
