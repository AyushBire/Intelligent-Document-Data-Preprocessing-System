"""Regression coverage for the redesign's API and processing dependencies."""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_idps.db"
os.environ["PRELOAD_MODELS"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app
from app.db import Base, get_db
from app.models.document import Document
from app.services import pipeline_service as pipeline


def test_large_image_is_resized_before_ocr(monkeypatch, tmp_path):
    """Keep preprocessing and OCR coordinates in the same resized image space.

    Args: monkeypatch: Environment fixture; tmp_path: Temporary directory.
    Returns: None. Raises: AssertionError on dimension regressions.
    """
    import cv2
    import numpy as np
    from processing.preprocessing import ImagePreprocessor
    monkeypatch.setenv("OCR_MAX_SIDE_PX", "1000")
    image = np.full((1200, 2400, 3), 255, np.uint8)
    source = tmp_path / "large.png"
    cv2.imwrite(str(source), image)
    loaded = ImagePreprocessor().load_image(str(source))
    assert loaded.shape[:2] == (500, 1000)


def test_deskew_corrects_a_rotated_page():
    """Check a rotated text block against its original horizontal layout.

    Returns: None. Raises: AssertionError if deskew rotates in the wrong direction.
    """
    import cv2
    import numpy as np
    from processing.preprocessing import ImagePreprocessor
    image = np.full((500, 700), 255, np.uint8)
    for y in (140, 190, 240, 290):
        cv2.rectangle(image, (150, y), (550, y + 20), 0, -1)
    rotation = cv2.getRotationMatrix2D((350, 250), 8, 1)
    tilted = cv2.warpAffine(image, rotation, (700, 500), borderValue=255)
    result = ImagePreprocessor().deskew(tilted)
    assert np.mean(cv2.absdiff(image, result)) < np.mean(cv2.absdiff(image, tilted)) / 4


def test_filtered_pagination_stats_file_and_bulk_delete(tmp_path):
    """Verify combined filters, totals, UTC stats and private file access.

    Args: tmp_path: Pytest temporary directory. Returns: None.
    Raises: AssertionError for contract regressions.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    from app.api.documents import settings
    root = tmp_path / "uploads"
    root.mkdir()
    image = root / "source.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"private")
    previous_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(root)

    async def seed():
        """Create isolated fixtures. Returns: None. Raises: Database errors."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            today = datetime.now(timezone.utc)
            for index, dtype in enumerate(["invoice", "receipt", "invoice"]):
                db.add(Document(filename=f"sample-{index}.png", file_path=str(image if index == 0 else outside),
                    document_type=dtype, ocr_text="common text", report="summary", raw_json=json.dumps({"number": index}),
                    created_at=today - timedelta(days=1) if index == 1 else today))
            await db.commit()

    async def override_db():
        """Yield the isolated test session. Returns: Async session. Raises: Database errors."""
        async with sessions() as db:
            yield db

    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            page = client.get("/api/documents", params={"search": "common", "document_type": "invoice", "limit": 1, "offset": 1})
            assert page.status_code == 200
            assert page.headers["x-total-count"] == "2"
            assert len(page.json()) == 1 and page.json()[0]["id"] == 1
            assert client.get("/api/documents", params={"limit": 0}).status_code == 422
            stats = client.get("/api/documents/stats").json()
            assert stats["total"] == 3 and stats["today"] == 2
            source = client.get("/api/documents/1/file")
            assert source.status_code == 200
            assert source.headers["cache-control"] == "private, no-store"
            assert source.headers["x-content-type-options"] == "nosniff"
            assert client.get("/api/documents/2/file").status_code == 404
            assert "file_path" not in client.get("/api/documents/1").json()
            assert client.get("/api/documents", params={"search": "%"}).json() == []
            assert client.delete("/api/documents", params=[("ids", 1)]).status_code == 204
            assert not image.exists()
    finally:
        app.dependency_overrides.clear()
        settings.UPLOAD_DIR = previous_dir
        asyncio.run(engine.dispose())


def test_failed_and_empty_extraction_never_saves(monkeypatch, tmp_path):
    """Reject blank OCR and failed or empty AI outputs before persistence.

    Args: monkeypatch: Patch fixture; tmp_path: Temporary directory.
    Returns: None. Raises: AssertionError on false-success regressions.
    """
    for text, output in [("", {}), ("text", {"error": "service failure"}), ("text", {"structured_data": {}})]:
        image = tmp_path / "upload.png"
        image.write_bytes(b"test")
        fake = SimpleNamespace(preprocessor=SimpleNamespace(process=lambda _: None),
            ocr=SimpleNamespace(process=lambda _: [], extract_text=lambda _: text),
            llm=SimpleNamespace(process=lambda _: output))
        monkeypatch.setattr(pipeline, "_get_pipeline", lambda: fake)
        monkeypatch.setattr(pipeline, "_semaphore", None)
        save = AsyncMock()
        job_id = pipeline.create_job()
        asyncio.run(pipeline.run_pipeline(job_id, str(image), save))
        assert pipeline.get_job(job_id).status == "error"
        save.assert_not_awaited()
        assert not image.exists()


def test_completion_notification_failure_keeps_saved_document(monkeypatch, tmp_path):
    """Keep successful extraction when a websocket disconnects.

    Args: monkeypatch: Patch fixture; tmp_path: Temporary directory.
    Returns: None. Raises: AssertionError on incorrect cleanup.
    """
    image = tmp_path / "upload.png"
    image.write_bytes(b"test")
    fake = SimpleNamespace(preprocessor=SimpleNamespace(process=lambda _: None),
        ocr=SimpleNamespace(process=lambda _: [], extract_text=lambda _: "document text"),
        llm=SimpleNamespace(process=lambda _: {"document_type": "invoice", "structured_data": {"number": 1}}))
    monkeypatch.setattr(pipeline, "_get_pipeline", lambda: fake)
    monkeypatch.setattr(pipeline, "_semaphore", None)
    save = AsyncMock(return_value=42)
    job_id = pipeline.create_job()
    asyncio.run(pipeline.run_pipeline(job_id, str(image), save, AsyncMock(side_effect=RuntimeError("disconnected"))))
    assert pipeline.get_job(job_id).status == "done"
    assert pipeline.get_job(job_id).document_id == 42
    assert image.exists()
