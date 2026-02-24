from fastapi import APIRouter

from .config import router as config_router
from .send import router as send_router
from .stats import router as stats_router
from .tasks import router as tasks_router
from .templates import router as templates_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(send_router)
api_router.include_router(tasks_router)
api_router.include_router(templates_router)
api_router.include_router(config_router)
api_router.include_router(stats_router)
