# Vercel backend migration

Status: backend deployed at https://idps-backend.vercel.app. The frontend proxy
uses this permanent backend. The free `idps-cloud-postgres` Neon database is in
Singapore, and migrations were applied over TLS. Private credentials are stored
in the `idps-backend` Vercel project environment. No laptop tunnel is required.

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

## Deployment configuration

The separate Vercel backend project uses root directory `backend`, the FastAPI
preset and region `sin1`. GitHub `main` triggers deployments. The frontend
project retains root directory `frontend` and proxies API and health requests to
the backend domain. The private variables listed below must exist before builds.

Vercel installs the lightweight dependencies from `backend/pyproject.toml` and
runs `alembic upgrade head` before deployment. Local EasyOCR and Docker installs
use `requirements-local.txt`; development dependencies include that file.

Validation completed: 18 tests passed against a disposable PostgreSQL database,
including upgrade/schema comparison/downgrade and legacy import compatibility.
The approved new Neon database and a real Gemini call were also tested together
using a generated synthetic invoice; only that synthetic document was deleted.
Existing local documents have not been migrated.

## Private backend environment

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
