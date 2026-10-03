import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models as _models  # noqa: F401  (registers all tables)
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.ws import router as ws_router
from app.config import get_settings
from app.db import Base, engine
from app.presentation_auth import PresentationAuthMiddleware
from app.services.pipeline_service import preload_pipeline

# Configure logging ONCE, here. Do not call basicConfig in other modules.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        # Dev convenience only. In production Alembic owns the schema.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready (create_all)")

    if settings.PRELOAD_MODELS:
        # Fail fast at boot (missing API key, model download problem, ...)
        await preload_pipeline()

    yield

    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Hide interactive docs in production
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Total-Count"],
)

if settings.PRESENTATION_AUTH_ENABLED:
    app.add_middleware(PresentationAuthMiddleware, username=settings.PRESENTATION_USERNAME,
                       password=settings.PRESENTATION_PASSWORD.get_secret_value())

app.include_router(health_router)
app.include_router(documents_router, prefix="/api")
app.include_router(ws_router)  # WebSocket — path is /ws/jobs/{id}


@app.get("/api/login", include_in_schema=False)
async def presentation_login():
    """Confirm browser login without displaying document data.

    Returns: Authentication status. Raises: None; middleware challenges invalid credentials.
    """
    return {"status": "authenticated" if settings.PRESENTATION_AUTH_ENABLED else "authentication not required"}
