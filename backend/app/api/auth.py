"""Browser sessions for protected presentation access."""
import secrets
import time
from http.cookies import SimpleCookie, CookieError
from fastapi import APIRouter, Request
from pydantic import BaseModel, SecretStr, Field
from starlette.responses import JSONResponse

COOKIE = 'idps_session'


class Credentials(BaseModel):
    """Login input with masked password representation."""
    username: str = Field(max_length=128)
    password: SecretStr = Field(max_length=1024)


def auth_router(auth):
    """Create session endpoints. Args: auth: Credential verifier or None. Returns: Router. Raises: None."""
    router = APIRouter(prefix='/api/auth')
    sessions = {}
    attempts = []

    def authenticated(scope):
        """Validate cookie expiry. Args: scope: ASGI request. Returns: Valid session. Raises: None."""
        cookie = SimpleCookie()
        try:
            cookie.load(dict(scope.get('headers', [])).get(b'cookie', b'').decode('latin1'))
            return sessions.get(cookie[COOKIE].value, 0) > time.time()
        except (KeyError, ValueError, CookieError):
            return False

    router.authenticated = authenticated

    @router.get('/session')
    async def status(request: Request):
        """Read session state. Args: request: HTTP request. Returns: Status. Raises: None."""
        return JSONResponse({'required': auth is not None, 'authenticated': auth is None or authenticated(request.scope)}, headers={'Cache-Control': 'no-store'})

    @router.post('/login')
    async def login(credentials: Credentials, request: Request):
        """Issue an eight-hour cookie. Args: credentials: Login; request: HTTP request. Returns: Session or error. Raises: None."""
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site login rejected'}, status_code=403)
        now = time.time()
        attempts[:] = [stamp for stamp in attempts if stamp > now - 300]
        if len(attempts) >= 20:
            return JSONResponse({'detail': 'Too many attempts. Try again in five minutes.'}, status_code=429)
        attempts.append(now)
        import base64
        header = b'Basic ' + base64.b64encode((credentials.username + ':' + credentials.password.get_secret_value()).encode())
        if auth is not None and not auth.authorized({'headers': [(b'authorization', header)]}):
            return JSONResponse({'detail': 'Incorrect username or password'}, status_code=401)
        for token in list(sessions):
            if sessions[token] <= now:
                del sessions[token]
        if len(sessions) >= 100:
            del sessions[next(iter(sessions))]
        token = secrets.token_urlsafe(32)
        sessions[token] = now + 28800
        response = JSONResponse({'authenticated': True}, headers={'Cache-Control': 'no-store'})
        response.set_cookie(COOKIE, token, max_age=28800, httponly=True, samesite='strict', secure=request.url.scheme == 'https' or request.headers.get('x-forwarded-proto') == 'https')
        return response

    @router.post('/logout')
    async def logout(request: Request):
        """Revoke the cookie. Args: request: HTTP request. Returns: Cleared session. Raises: None."""
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site logout rejected'}, status_code=403)
        cookie = SimpleCookie()
        cookie.load(request.headers.get('cookie', ''))
        if COOKIE in cookie:
            sessions.pop(cookie[COOKIE].value, None)
        response = JSONResponse({'authenticated': False}, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(COOKIE, httponly=True, samesite='strict')
        return response

    return router
