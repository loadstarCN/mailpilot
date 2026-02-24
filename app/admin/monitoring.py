import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.session import get_db
from ..models.admin import Admin
from ..services import stats_service
from ..worker.events import event_bus
from ..worker.state import worker_state
from .deps import get_current_admin

router = APIRouter(prefix="/monitoring")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def monitoring_page(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    return templates.TemplateResponse(
        "monitoring/index.html",
        {"request": request, "admin": admin},
    )


@router.get("/sse")
async def monitoring_sse(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    async def event_stream():
        queue = event_bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.dumps({
                        "task_id": event.task_id,
                        "project": event.project_name,
                        "to": event.to,
                        "subject": event.subject,
                        "status": event.status,
                        "error": event.error,
                        "timestamp": event.timestamp.isoformat(),
                    })
                    yield f"event: send_event\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: \n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/trend")
async def trend_api(
    period: str = "day",
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    import uuid

    pid = uuid.UUID(project_id) if project_id else None
    return await stats_service.get_trend(db, period, pid)


@router.get("/api/queue-depth")
async def queue_depth_api(
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return await stats_service.get_queue_depth(db)


@router.get("/api/worker-status")
async def worker_status_api(
    admin: Admin = Depends(get_current_admin),
):
    return {
        "running": worker_state.running,
        "concurrency": settings.worker_concurrency,
        "active_tasks": worker_state.active_count,
        "uptime_seconds": round(worker_state.uptime_seconds, 1),
    }
