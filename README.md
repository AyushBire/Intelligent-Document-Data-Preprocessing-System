# Intelligent Document Processing System (IDPS)

IDPS is a React and FastAPI workspace for extracting structured information from document images, reviewing the results, and exporting JSON, CSV and text reports. It preserves the existing OpenCV → EasyOCR → Gemini pipeline.

## Features

- Browse, drop or paste JPG, PNG, BMP and TIFF images up to 20 MB. PDF is not supported.
- Preview before extraction and follow real processing progress.
- Review fields, nested JSON, summaries, source images and raw OCR text.
- Edit extracted fields and summaries; export JSON, CSV and TXT.
- Search, filter, paginate and delete documents with confirmation.
- Responsive dashboard, mobile navigation and keyboard-accessible dialogs and result tabs.

## Project Structure

- `frontend/`: React 19, Vite, strict TypeScript, Tailwind v3, TanStack Query and axios.
- `backend/app/`: FastAPI routes, SQLAlchemy models, schemas and services.
- `backend/processing/`: preserved preprocessing, OCR and Gemini extraction code.
- `backend/alembic/`: initial schema migration for SQLite and PostgreSQL.
- `docker-compose.yml`: PostgreSQL, single-worker API and authenticated nginx frontend.
- `docs/FOLLOW_UP.md`: implementation status, verification and remaining launch checks.
- `app.py` and `Database/`: retained legacy artifacts, outside the supported web workflow.

## Setup

Use Python 3.11/3.12 and Node.js 22. Copy `.env.example` to `.env` without overwriting existing credentials, and set `GEMINI_API_KEY` and `POSTGRES_PASSWORD`. PostgreSQL is the default for development and deployment; run the database and apply migrations before starting the API. See [Deployment guide](docs/DEPLOYMENT.md).

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Start the API from `backend/` so its imports and relative storage paths resolve correctly. Settings load the root `.env`, then an optional ignored `backend/.env`; process environment variables take precedence.

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api`, `/ws` and `/health` to the API. Development and production use PostgreSQL with Alembic migrations. SQLite remains available only through an explicit test/import override.

## Validation

```powershell
cd frontend
npm run lint
npm run build
cd ../backend
..\.venv\Scripts\python.exe -m pytest -q
```

On a fresh database, run `alembic upgrade head` from `backend/` before setting `AUTO_CREATE_TABLES=false`. For an existing database created with `create_all`, back it up and compare its schema before using `alembic stamp head`; do not blindly run the initial migration or reset existing data.

## Containers

1. Fill the root `.env` with a valid Gemini key and a strong `POSTGRES_PASSWORD`.
2. Create `deploy/.htpasswd` with Apache `htpasswd`; keep it out of Git.
3. Run `docker compose up -d --build` from the repository root.
4. Wait for backend readiness, then open `http://localhost:8080` and authenticate.

The backend applies migrations before starting one uvicorn worker. The first model load can download EasyOCR weights and require additional startup time. Provide at least 4 GB RAM. Compose exposes nginx only on loopback; the production override adds Caddy with automatic HTTPS. See [Deployment guide](docs/DEPLOYMENT.md) for VM setup, data import and backups. `GET /health` is public liveness; backend `GET /health/ready` also checks the database and model initialization. The nginx request limit includes multipart overhead above the API's 20 MB file cap.

## Database presentation viewer

An optional pgAdmin interface can display the deployed PostgreSQL tables, extracted data, queries and relationships during your presentation. See [Database presentation guide](docs/DATABASE_PRESENTATION.md) for startup commands and a five-minute demonstration. It is separate from the normal deployment configuration.

## Environment Variables

See `.env.example`. Important settings: `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL`, `AUTO_CREATE_TABLES`, `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`, `MAX_CONCURRENT_JOBS`, `OCR_MAX_SIDE_PX`, `PRELOAD_MODELS`, `CORS_ORIGINS` and `DEBUG`. Keep the UI's 20 MB validation in sync if changing the server upload cap. `stats.today` counts the current UTC calendar day and is labeled accordingly.

## Notes

- Uploaded files and extracted data are stored on the server. OCR text is sent to Gemini. Review AI-generated values before use.
- The browser stores only active job metadata, never full completed-document contents.
- Jobs are in memory and expire after completion; a restart invalidates active job IDs. Keep one backend worker.
- Basic authentication provides a shared presentation login. The production override supplies HTTPS; define data retention, test backups and check Gemini credentials/quota before public use.
- Docker execution and a real OCR/Gemini extraction remain launch verification steps; see `docs/FOLLOW_UP.md`.
- Never commit `.env`, `.htpasswd`, uploads or database files.
