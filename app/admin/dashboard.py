from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import stats_service
from .deps import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    overview = await stats_service.get_overview(db)
    queue_depth = await stats_service.get_queue_depth(db)
    smtp_health = await stats_service.get_smtp_health(db)
    recent_failures = await stats_service.get_recent_failures(db, limit=10)
    project_ranking = await stats_service.get_project_ranking(db)

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "admin": admin,
            "overview": overview,
            "queue_depth": queue_depth,
            "smtp_health": smtp_health,
            "recent_failures": recent_failures,
            "project_ranking": project_ranking,
        },
    )
