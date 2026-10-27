# Vercel backend migration

Status: migration in progress. The existing frontend still uses its configured
backend tunnel; the cloud backend has not been provisioned or deployed yet.

## Implemented

- `backend/vercel.json` configures FastAPI and a 300-second function duration.
- `.vercelignore` excludes local credentials, databases and uploaded documents.
- `SERVERLESS_MODE` requires authentication, PostgreSQL, disabled local model
  preloading and an upload limit at most 4 MB.
- Cloud database connections use TLS and no persistent application connection
  pool, avoiding event-loop reuse and excessive idle connections.
- Browser sessions, credential versions and login rate limits are database-backed.
- Session tokens are random, stored only as hashes, expire after eight hours,
  and are revoked by logout or credential rotation.
- Job status is persisted; interrupted invocations become retryable errors.
- Alembic revision `0002_cloud_runtime` adds the runtime tables.
- Cloud processing sends normalized images to Gemini within a bounded request;
  it does not depend on post-response background execution or local OCR weights.
- Private JPEG source images are stored with their records in PostgreSQL and
  served only through the authenticated API. Deletion cascades to the image.
- The frontend reads runtime upload limits and allows time for cloud processing.
- New cloud uploads were approved by the user; existing local records stay local.

## Still required before deployment

1. Complete the account-security prompt in Vercel.
2. Provision a free cloud PostgreSQL database and connect its secret URL.
3. Create a separate Vercel backend project with root directory `backend`.
4. Set private environment variables, run migrations, deploy, verify login and a
   synthetic upload, and only then replace the frontend tunnel rewrites.

Vercel installs the lightweight dependencies from `backend/pyproject.toml` and
runs `alembic upgrade head` before deployment. Local EasyOCR and Docker installs
use `requirements-local.txt`; development dependencies include that file.

## Planned private environment

```dotenv
SERVERLESS_MODE=true
DATABASE_URL=postgresql://USER:PASSWORD@CLOUD_HOST/DATABASE?sslmode=require
PRESENTATION_AUTH_ENABLED=true
PRESENTATION_USERNAME=SET_PRIVATELY
PRESENTATION_PASSWORD=SET_PRIVATELY
GEMINI_API_KEY=SET_PRIVATELY
GEMINI_MODEL=SET_PRIVATELY
PRELOAD_MODELS=false
MAX_UPLOAD_SIZE_MB=4
AUTO_CREATE_TABLES=false
```

Credentials belong in Vercel's environment settings, never in Git or `vercel.json`.
