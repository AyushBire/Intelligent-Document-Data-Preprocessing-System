"""Verify authentication across independent serverless instances."""
import asyncio
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient
from app.api import cloud_auth
from app.db import Base
from app.models.cloud import BrowserSession
from app.presentation_auth import PresentationAuthMiddleware


def make_app(password: str = "test-password") -> FastAPI:
    """Create an isolated function instance. Args: password: Login secret. Returns: App. Raises: None."""
    app = FastAPI()
    verifier = PresentationAuthMiddleware(app, "presenter", password)
    router = cloud_auth.cloud_auth_router(verifier)
    app.include_router(router)
    app.add_middleware(PresentationAuthMiddleware, username="presenter", password=password, session_check=router.authenticated)

    @app.get("/api/private")
    async def private():
        """Return a protected fixture. Returns: Result. Raises: None."""
        return {"ok": True}

    return app


def test_shared_sessions_revocation_rotation_and_expiry(tmp_path, monkeypatch):
    """Verify sessions survive instance changes and obey revocation.

    Args: tmp_path: Temporary database; monkeypatch: Dependency override.
    Returns: None. Raises: AssertionError on an access-control regression.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}", poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cloud_auth, "AsyncSessionLocal", sessions)

    async def initialize():
        """Create isolated tables. Returns: None. Raises: Database errors."""
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(initialize())
    credentials = {"username": "presenter", "password": "test-password"}
    with TestClient(make_app(), base_url="https://testserver") as first, TestClient(make_app(), base_url="https://testserver") as second:
        assert first.get("/api/private").status_code == 401
        assert first.post("/api/auth/login", json=credentials).status_code == 200
        token = first.cookies.get("idps_session")
        second.cookies.set("idps_session", token)
        assert second.get("/api/private").status_code == 200
        with TestClient(make_app("rotated-password"), base_url="https://testserver") as rotated:
            rotated.cookies.set("idps_session", token)
            assert rotated.get("/api/private").status_code == 401
        assert second.post("/api/auth/logout").status_code == 200
        assert first.get("/api/private").status_code == 401
        assert first.post("/api/auth/login", json=credentials).status_code == 200

        async def expire():
            """Expire stored sessions. Returns: None. Raises: Database errors."""
            async with sessions() as db:
                await db.execute(update(BrowserSession).values(expires_at=0))
                await db.commit()

        asyncio.run(expire())
        assert first.get("/api/auth/session").json()["authenticated"] is False
        assert first.post("/api/auth/login", json=credentials, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    asyncio.run(engine.dispose())
