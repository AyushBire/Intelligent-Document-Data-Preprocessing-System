"""Protect temporary public presentation access with HTTP Basic authentication."""
import base64
import binascii
import hashlib
import secrets

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class PresentationAuthMiddleware:
    """Authenticate HTTP and WebSocket requests without buffering uploaded images."""

    def __init__(self, app: ASGIApp, username: str, password: str, session_check=None) -> None:
        """Store fixed-length credential digests.

        Args: app: Wrapped application; username: Login name; password: Login secret.
        Returns: None. Raises: None.
        """
        self.app = app
        self.session_check = session_check
        self.username = hashlib.sha256(username.encode()).digest()
        self.password = hashlib.sha256(password.encode()).digest()

    def authorized(self, scope: Scope) -> bool:
        """Check a Basic authorization header in constant time.

        Args: scope: ASGI request scope. Returns: Credential match. Raises: None.
        """
        headers = dict(scope.get("headers", []))
        try:
            scheme, encoded = headers.get(b"authorization", b"").split(b" ", 1)
            if scheme.lower() != b"basic":
                return False
            username, password = base64.b64decode(encoded, validate=True).decode("utf-8").split(":", 1)
        except (ValueError, UnicodeError, binascii.Error):
            return False
        user_matches = secrets.compare_digest(hashlib.sha256(username.encode()).digest(), self.username)
        password_matches = secrets.compare_digest(hashlib.sha256(password.encode()).digest(), self.password)
        return user_matches and password_matches

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject unauthenticated traffic while permitting non-sensitive liveness.

        Args: scope: Request scope; receive: Incoming events; send: Outgoing events.
        Returns: None. Raises: Downstream application errors.
        """
        if self.session_check and self.session_check(scope):
            await self.app(scope, receive, send)
            return
        if scope.get("path") in {"/api/auth/session", "/api/auth/login", "/api/auth/logout"}:
            await self.app(scope, receive, send)
            return
        if scope["type"] not in {"http", "websocket"} or (
            scope["type"] == "http" and scope.get("method") == "GET" and scope.get("path") == "/health"
        ) or self.authorized(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse({"detail": "Presentation login required"}, status_code=401,
                                headers={"Cache-Control": "no-store"})
        await response(scope, receive, send)
