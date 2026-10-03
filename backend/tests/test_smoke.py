import os

# Must be set before the app is imported
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_idps.db"
os.environ["PRELOAD_MODELS"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "true"

import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app
from processing.preprocessing import ImagePreprocessor


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"


def test_stats_empty_db_works():
    with TestClient(app) as client:
        r = client.get("/api/documents/stats")
        assert r.status_code == 200
        assert "total" in r.json()


def test_upload_rejects_non_image_even_if_content_type_lies():
    with TestClient(app) as client:
        r = client.post(
            "/api/documents/upload",
            files={"file": ("evil.png", b"this is not an image", "image/png")},
        )
        assert r.status_code == 415


def test_upload_rejects_pdf():
    with TestClient(app) as client:
        r = client.post(
            "/api/documents/upload",
            files={"file": ("a.pdf", b"%PDF-1.7 ...", "application/pdf")},
        )
        assert r.status_code == 415


def test_deskew_leaves_a_straight_page_alone():
    # Regression test: OpenCV >= 4.5 changed the minAreaRect angle convention.
    img = np.full((400, 600), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (550, 100), 0, -1)
    cv2.rectangle(img, (50, 150), (550, 200), 0, -1)

    out = ImagePreprocessor().deskew(img)

    assert np.mean(cv2.absdiff(img, out)) < 1
