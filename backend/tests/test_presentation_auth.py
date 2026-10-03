"""Verify authentication before exposing document endpoints through a tunnel."""
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation_auth import PresentationAuthMiddleware


async def endpoint(request):
    """Return fixture data. Args: request: HTTP request. Returns: JSON response. Raises: None."""
    return JSONResponse({"ok": True})


def test_presentation_login_protects_data_and_accepts_valid_credentials():
    """Test the access boundary. Returns: None. Raises: AssertionError on auth regressions."""
    app = Starlette(routes=[Route("/health", endpoint), Route("/api/documents", endpoint), Route("/health/ready", endpoint)])
    app.add_middleware(PresentationAuthMiddleware, username="presenter", password="test-password")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/ready").status_code == 401
        response = client.get("/api/documents")
        assert response.status_code == 401
        assert "WWW-Authenticate" not in response.headers
        assert client.get("/api/documents", auth=("presenter", "wrong")).status_code == 401
        assert client.get("/api/documents", headers={"Authorization": "Basic !!!"}).status_code == 401
        assert client.get("/api/documents", auth=("presenter", "test-password")).status_code == 200
