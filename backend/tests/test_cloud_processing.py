"""Exercise approved cloud processing with synthetic images and mocked inference."""
import asyncio
import io
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.api import documents
from app.db import Base, get_db
from app.models.cloud import DocumentFile
from app.models.document import Document
from app.services import cloud_jobs, cloud_processing
from main import app


def test_cloud_upload_private_file_failure_and_deletion(tmp_path, monkeypatch):
    """Verify persistence, images, failures and deletion without external AI calls.

    Args: tmp_path: Temporary storage; monkeypatch: Isolated dependencies.
    Returns: None. Raises: AssertionError on data-integrity or API regressions.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cloud.db'}", poolclass=NullPool)

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _record):
        """Enforce SQLite foreign keys. Args: connection: DB handle; _record: Pool metadata. Returns: None. Raises: Database errors."""
        connection.execute("PRAGMA foreign_keys=ON")

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cloud_processing, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(cloud_jobs, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(documents.settings, "SERVERLESS_MODE", True)
    monkeypatch.setattr(documents.settings, "MAX_UPLOAD_SIZE_MB", 4)
    monkeypatch.setattr(cloud_processing, "extract_image", lambda _image: {
        "document_type": "invoice", "ocr_text": "SYNTHETIC Invoice DEMO-1 Total 10",
        "report": "Synthetic fixture", "structured_data": {"invoice_number": "DEMO-1", "total": 10}})

    async def initialize():
        """Create isolated schema. Returns: None. Raises: Database errors."""
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def database():
        """Yield fixture transactions. Yields: Session. Raises: Database errors."""
        async with sessions() as db:
            yield db

    async def remaining():
        """Count persistent records. Returns: Document/file counts. Raises: Database errors."""
        async with sessions() as db:
            return len((await db.scalars(select(Document))).all()), len((await db.scalars(select(DocumentFile))).all())

    asyncio.run(initialize())
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="PNG")
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            response = client.post("/api/documents/upload", files={"file": ("synthetic.png", buffer.getvalue(), "image/png")})
            assert response.status_code == 202
            job = client.get(f"/api/documents/jobs/{response.json()['job_id']}").json()
            assert job["status"] == "done"
            identifier = job["document_id"]
            image = client.get(f"/api/documents/{identifier}/file")
            assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
            assert image.headers["cache-control"] == "private, no-store"
            assert asyncio.run(remaining()) == (1, 1)
            assert client.delete(f"/api/documents/{identifier}").status_code == 204
            assert asyncio.run(remaining()) == (0, 0)
            assert client.post("/api/documents/upload", files={"file": ("broken.png", b"\x89PNG\r\n\x1a\ninvalid")}).status_code == 422

            def failed(_image):
                """Simulate provider failure. Args: _image: Image bytes. Returns: Never. Raises: RuntimeError."""
                raise RuntimeError("Synthetic provider failure")

            monkeypatch.setattr(cloud_processing, "extract_image", failed)
            response = client.post("/api/documents/upload", files={"file": ("synthetic.png", buffer.getvalue())})
            job = client.get(f"/api/documents/jobs/{response.json()['job_id']}").json()
            assert job["status"] == "error"
            assert asyncio.run(remaining()) == (0, 0)
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
