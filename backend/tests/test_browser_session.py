"""Verify cookie lifecycle and document access boundaries."""
from fastapi import FastAPI
from starlette.testclient import TestClient
from app.api.auth import auth_router
from app.presentation_auth import PresentationAuthMiddleware


def test_session_login_logout_and_expiry():
    """Exercise login, secure cookies and revocation. Returns: None. Raises: AssertionError on regression."""
    app = FastAPI()
    verifier = PresentationAuthMiddleware(app, 'presenter', 'test-password')
    router = auth_router(verifier)
    app.include_router(router)
    app.add_middleware(PresentationAuthMiddleware, username='presenter', password='test-password', session_check=router.authenticated)

    @app.get('/api/private')
    async def private():
        """Return protected fixture. Returns: Data. Raises: None."""
        return {'ok': True}

    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/api/auth/session').json()['authenticated'] is False
        assert client.get('/api/private').status_code == 401
        assert client.post('/api/auth/login', json={'username': 'presenter', 'password': 'wrong'}).status_code == 401
        response = client.post('/api/auth/login', json={'username': 'presenter', 'password': 'test-password'})
        assert response.status_code == 200
        assert 'HttpOnly' in response.headers['set-cookie']
        assert 'Secure' in response.headers['set-cookie']
        assert client.get('/api/private').status_code == 200
        cookie = client.cookies.get('idps_session')
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/private').status_code == 401
        assert client.get('/api/private', headers={'Cookie': f'idps_session={cookie}'}).status_code == 401
        assert client.post('/api/auth/login', headers={'Sec-Fetch-Site': 'cross-site'}, json={'username': 'presenter', 'password': 'test-password'}).status_code == 403
