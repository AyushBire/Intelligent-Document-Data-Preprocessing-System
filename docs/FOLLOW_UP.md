# Shared-chat follow-up

The visible [Claude conversation](https://claude.ai/share/d8c2679e-a465-4f5f-add6-f87f75bfb567) contains a read-only audit and a six-phase implementation plan. The final attachments and command output are hidden in the shared snapshot. This implementation follows the visible plan and checks each claim against the repository.

| Phase | Implemented |
| --- | --- |
| Build foundation | Frontend dependencies and lockfile, strict TypeScript, root Compose, backend Dockerfile, initial Alembic migration, deskew correction, bounded image size, centralized logging, explicit extraction errors |
| Design system | Original light SaaS interface, responsive shell, accessible native dialogs, common buttons, errors, loading and empty states |
| Extraction | Browse/drop/paste, validation, local preview, explicit extract action, real progress polling, job resume, expired-job recovery, privacy copy |
| Results | Overview, fields, JSON, summary, source and OCR tabs; typed field editing and validated JSON drafts; copy and JSON/CSV/TXT exports; source zoom/rotation |
| Dashboard/history | Real UTC daily count, type distribution, recent documents, combined search/type filters, pagination totals, confirmed bulk deletion, legacy URL redirects |
| Readiness | Error boundary, 404 page, health status, CSP, clean build/lint scripts, regression tests, CI container-build checks, deployment documentation |

## Preserved contracts

- React/Vite/TypeScript/Tailwind v3, FastAPI, EasyOCR, Gemini, SQLAlchemy and existing model tables.
- `POST /api/documents/upload` returns HTTP 202 with `{job_id, filename}`; job polling still uses the original status/stage/progress contract.
- Public document responses retain the existing shape, with no server filesystem paths.
- List responses remain arrays. `X-Total-Count`, `stats.today` and `GET /api/documents/{id}/file` are additive.
- The legacy `/process` and `/database?id=...` URLs redirect to the new routes. Legacy Streamlit and `Database/` files remain available.

## Verification

- Clean `npm ci`, strict TypeScript/Vite production build and lint without warnings.
- Thirteen passing backend regression tests cover processing/API behavior, PostgreSQL configuration, imports, relationships, rollback of database rows and copied images, refusal to overwrite data, and future ID allocation.
- Alembic upgrade, metadata comparison and downgrade verified against PostgreSQL 16.15 in a disposable test database; previous SQLite migration checks also passed.
- The running API now uses PostgreSQL. Two original backend documents and one real user upload from the isolated preview were preserved with their source images. Synthetic preview records were excluded; the separate legacy database was retained.
- Browser checks use a separate synthetic database: dashboard statistics, pagination, nested results, source preview and invalid JSON retention. Layouts checked at 360, 768, 1024 and 1440 pixels.

## Remaining launch checks

- Docker is unavailable on the local host. The Compose/Caddy/nginx stack still needs execution on the target VM, including ARM container validation if using Oracle Ampere. PostgreSQL migrations and imports have been executed locally. CI includes container builds and PostgreSQL checks; its remote execution has not been observed here.
- A full EasyOCR → Gemini extraction still needs a synthetic or approved sample and valid credentials. API integration and pipeline error behavior were checked without uploading personal documents to an AI service.
- Production HTTPS and private pgAdmin configuration are provided. Confirm DNS, certificate issuance, login, backup restoration, retention policy and Gemini credentials/quota on the actual VM. Multi-worker processing still requires shared job storage; keep one worker.
- Root `node_modules/` may remain as an ignored local cache. Production installs now resolve entirely from `frontend/`.
