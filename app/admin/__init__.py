from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from .account import router as account_router
from .api_docs import router as api_docs_router
from .auth import router as auth_router
from .csrf import csrf_protect
from .dashboard import router as dashboard_router
from .deps import _RedirectToLogin
from .email_templates import router as email_templates_router
from .monitoring import router as monitoring_router
from .projects import router as projects_router
from .smtp_configs import router as smtp_configs_router
from .tasks import router as tasks_router

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(csrf_protect)])
admin_router.include_router(auth_router)
admin_router.include_router(dashboard_router)
admin_router.include_router(projects_router)
admin_router.include_router(smtp_configs_router)
admin_router.include_router(email_templates_router)
admin_router.include_router(tasks_router)
admin_router.include_router(monitoring_router)
admin_router.include_router(account_router)
admin_router.include_router(api_docs_router)


@admin_router.get("")
async def admin_index():
    return RedirectResponse(url="/admin/dashboard", status_code=303)
