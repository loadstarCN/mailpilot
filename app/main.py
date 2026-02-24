import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .admin import admin_router
from .admin.deps import _RedirectToLogin
from .api import api_router
from .config import settings
from .db.session import close_db, init_db
from .services.admin_service import ensure_default_admin
from .worker.loop import worker_loop
from .worker.state import worker_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.database_url)

    from .db.session import async_session_maker

    async with async_session_maker() as db:
        await ensure_default_admin(
            db, settings.admin_default_username, settings.admin_default_password
        )

    worker_task = asyncio.create_task(worker_loop())
    yield
    worker_state.running = False
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_db()


app = FastAPI(title="Mailpilot", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
app.include_router(admin_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(_RedirectToLogin)
async def redirect_to_login_handler(request: Request, exc: _RedirectToLogin):
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse(url="/admin/dashboard", status_code=303)
