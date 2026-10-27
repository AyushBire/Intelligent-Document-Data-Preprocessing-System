# Vercel backend migration

Status: code and cloud database verified. The free `idps-cloud-postgres` Neon
database is provisioned in Singapore and migrations have been applied over TLS.
The backend Vercel deployment is awaiting approval to import its private environment
variables. The existing frontend still uses its configured backend tunnel.

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

1. Approve importing the existing Gemini key, admin credentials and Neon URL as
   private environment variables into the `idps-backend` Vercel project.
2. Deploy the prepared FastAPI project with root directory `backend`.
3. Verify login and a
   synthetic upload, and only then replace the frontend tunnel rewrites.

Vercel installs the lightweight dependencies from `backend/pyproject.toml` and
runs `alembic upgrade head` before deployment. Local EasyOCR and Docker installs
use `requirements-local.txt`; development dependencies include that file.

Validation completed: 18 tests passed against a disposable PostgreSQL database,
including upgrade/schema comparison/downgrade and legacy import compatibility.
The approved new Neon database and a real Gemini call were also tested together
using a generated synthetic invoice; only that synthetic document was deleted.
Existing local documents have not been migrated.

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
