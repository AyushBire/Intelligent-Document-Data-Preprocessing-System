from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.services.pipeline_service import pipeline_ready

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health():
    """Liveness — the process is up."""
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/health/ready")
async def ready():
    """Readiness — DB reachable and models loaded."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")

    if settings.PRELOAD_MODELS and not pipeline_ready():
        raise HTTPException(status_code=503, detail="models still loading")

    return {"status": "ready"}
