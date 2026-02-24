"""CSRF 防护：基于 session cookie 的 HMAC token"""

import hashlib
import hmac

from fastapi import Depends, HTTPException, Request

from ..config import settings

# 登录页不需要 CSRF（还没有 session）
CSRF_EXEMPT_PATHS = {"/admin/login"}


def generate_csrf_token(session_cookie: str) -> str:
    """基于 session cookie + secret_key 生成确定性 CSRF token"""
    key = settings.secret_key.encode()
    return hmac.new(key, session_cookie.encode(), hashlib.sha256).hexdigest()


async def csrf_protect(request: Request):
    """FastAPI 依赖：为所有请求生成 token，POST 请求额外验证"""
    session_cookie = request.cookies.get("mp_session", "")
    request.state.csrf_token = (
        generate_csrf_token(session_cookie) if session_cookie else ""
    )

    if request.method == "POST" and request.url.path not in CSRF_EXEMPT_PATHS:
        if not session_cookie:
            return  # 无 session，后续 get_current_admin 会拦截
        form = await request.form()
        submitted = form.get("_csrf_token", "")
        if not hmac.compare_digest(submitted, request.state.csrf_token):
            raise HTTPException(status_code=403, detail="CSRF token 验证失败")
