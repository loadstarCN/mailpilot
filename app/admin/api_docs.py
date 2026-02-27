from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..models.admin import Admin
from .deps import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory="templates")

API_MD_PATH = Path(__file__).resolve().parents[2] / "docs" / "api.md"


@router.get("/api-docs", response_class=HTMLResponse)
async def api_docs(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    return templates.TemplateResponse(
        "api_docs/index.html",
        {"request": request, "admin": admin},
    )


@router.get("/api-docs/download")
async def api_docs_download(
    admin: Admin = Depends(get_current_admin),
):
    return FileResponse(
        path=str(API_MD_PATH),
        filename="mailpilot-api.md",
        media_type="text/markdown",
    )
