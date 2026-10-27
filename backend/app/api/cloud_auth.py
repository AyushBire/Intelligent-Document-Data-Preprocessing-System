"""Database-backed browser authentication for independently scaled functions."""
import base64
import hashlib
import secrets
import time
from http.cookies import CookieError, SimpleCookie
from fastapi import APIRouter, Request
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from starlette.responses import JSONResponse
from app.api.auth import COOKIE, Credentials
from app.db import AsyncSessionLocal
from app.models.cloud import BrowserSession, LoginAttempt


def read_token(scope: dict) -> str:
    """Read the private session cookie. Args: scope: ASGI request. Returns: Token or empty string. Raises: None."""
    cookies = SimpleCookie()
    try:
        cookies.load(dict(scope.get("headers", [])).get(b"cookie", b"").decode("latin1"))
        return cookies[COOKIE].value if COOKIE in cookies else ""
    except (CookieError, ValueError):
        return ""


def digest(value: str) -> str:
    """Hash a secret for lookup. Args: value: Secret. Returns: SHA256 digest. Raises: None."""
    return hashlib.sha256(value.encode()).hexdigest()


def cloud_auth_router(auth) -> APIRouter:
    """Build durable authentication routes. Args: auth: Credential verifier. Returns: Router. Raises: Database errors."""
    router = APIRouter(prefix="/api/auth")
    version = hashlib.sha256(auth.username + auth.password).hexdigest()

    async def authenticated(scope: dict) -> bool:
        """Validate a durable session. Args: scope: ASGI request. Returns: Authorization. Raises: Database errors."""
        token = read_token(scope)
        if not token:
            return False
        async with AsyncSessionLocal() as db:
            session = await db.get(BrowserSession, digest(token))
            return bool(session and session.expires_at > time.time() and secrets.compare_digest(session.credential_version, version))

    router.authenticated = authenticated

    @router.get("/session")
    async def status(request: Request):
        """Read auth status. Args: request: HTTP request. Returns: Private status. Raises: Database errors."""
        return JSONResponse({"required": True, "authenticated": await authenticated(request.scope)}, headers={"Cache-Control": "no-store"})

    @router.post("/login")
    async def login(credentials: Credentials, request: Request):
        """Verify credentials and create a revocable session. Args: credentials: Login; request: HTTP request. Returns: Cookie or error. Raises: Database errors."""
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site login rejected"}, status_code=403)
        now = int(time.time())
        address = request.headers.get("x-vercel-forwarded-for", request.client.host if request.client else "unknown")
        key = digest(f"{address}:{now // 300}")
        async with AsyncSessionLocal() as db:
            await db.execute(delete(LoginAttempt).where(LoginAttempt.expires_at < now))
            await db.execute(delete(BrowserSession).where(BrowserSession.expires_at < now))
            attempt = insert(LoginAttempt).values(key=key, count=1, expires_at=now + 300)
            count = (await db.execute(attempt.on_conflict_do_update(index_elements=[LoginAttempt.key], set_={"count": LoginAttempt.count + 1}).returning(LoginAttempt.count))).scalar_one()
            await db.commit()
            if count > 20:
                return JSONResponse({"detail": "Too many attempts. Try again in five minutes."}, status_code=429, headers={"Retry-After": "300"})
            header = b"Basic " + base64.b64encode(f"{credentials.username}:{credentials.password.get_secret_value()}".encode())
            if not auth.authorized({"headers": [(b"authorization", header)]}):
                return JSONResponse({"detail": "Incorrect username or password"}, status_code=401, headers={"Cache-Control": "no-store"})
            token = secrets.token_urlsafe(32)
            db.add(BrowserSession(token_hash=digest(token), credential_version=version, expires_at=now + 28800))
            await db.commit()
        response = JSONResponse({"authenticated": True}, headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE, token, max_age=28800, httponly=True, secure=True, samesite="strict")
        return response

    @router.post("/logout")
    async def logout(request: Request):
        """Revoke access across instances. Args: request: HTTP request. Returns: Cookie removal. Raises: Database errors."""
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site logout rejected"}, status_code=403)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(BrowserSession).where(BrowserSession.token_hash == digest(read_token(request.scope))))
            await db.commit()
        response = JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="strict")
        return response

    return router
