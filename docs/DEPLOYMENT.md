# PostgreSQL deployment

The supported web backend uses PostgreSQL through asyncpg. SQLite is retained only for regression tests and importing legacy records. Alembic owns the production schema; automatic table creation is disabled by default. API contracts and existing document tables are preserved.

## Architecture

```text
Browser → Caddy (HTTPS) → nginx (login + React) → FastAPI → PostgreSQL
                                                  ├─ uploads volume
                                                  ├─ EasyOCR model cache
                                                  └─ Gemini API
```

Use an Oracle Ubuntu VM with Docker Engine and the Compose plugin, sufficient persistent storage and at least 4 GB RAM. The Docker dependencies include published Python 3.11 ARM64 CPU wheels, but this repository's container has not yet been executed on an ARM VM. Keep one API worker because processing jobs reside in memory. Free hosting does not make Gemini usage free.

## Local PostgreSQL development

### Current Windows workspace

The backend has already been switched to PostgreSQL 16.15 on `127.0.0.1:55432`. Its password and connection settings are in the ignored root `.env`. The old backend SQLite data and the one real preview upload are now in PostgreSQL, with three documents and source images in `backend/uploads_postgres/`. Original databases and import snapshots are retained. The legacy four-document database is separate.

The portable server data is stored in `.validation/postgres-data/`. Preserve that directory until you have exported a verified backup. After reboot, start the database from the repository root:

```powershell
& '.validation/pg-runtime/pgsql/bin/pg_ctl.exe' -D '.validation/postgres-data' -l '.validation/postgres.log' -o '-h 127.0.0.1 -p 55432' start
```

Then run the API from `backend/`. This portable setup supports the current workspace; the deployment uses persistent Docker volumes. For a fresh Docker database on the usual native development port, set `POSTGRES_PORT=5432` in the local `.env`. The container backend always uses its internal port 5432.

### Fresh setup

1. Preserve your existing `.env` and fill in missing keys from `.env.example`. Set a strong `POSTGRES_PASSWORD`, valid Gemini credentials and the actual supported Gemini model.
2. Run `docker compose up -d db` from the repository root. PostgreSQL is private to Docker by default. For a native development API, publish only a loopback database port using the override below.
3. From `backend/`, run `python -m alembic upgrade head`, then `python -m uvicorn main:app --reload`. Use the repository virtual environment when necessary.

Create an ignored `docker-compose.local.yml`:

```yaml
services:
  db:
    ports:
      - "127.0.0.1:5432:5432"
```

Start it with `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d db`. Set `POSTGRES_HOST=localhost` for the native API. The container API uses `db` automatically. Passwords in separate `POSTGRES_*` settings are handled safely, including special characters. Hosted connection strings can instead use `DATABASE_URL=postgresql://...`; passwords in URLs must be percent encoded. Configure verified provider TLS, for example `?ssl=verify-full` with the provider's CA configuration where required. Do not disable TLS for a remote database.

## Public VM deployment

1. Point a DNS hostname at the VM. Allow incoming TCP 80/443 and restricted SSH in both the cloud security rules and host firewall. Keep ports 5432, 8000 and 5050 private.
2. Clone the project, configure the ignored `.env`, and set `DOMAIN` to that hostname without `https://` or a path. Preserve a valid Gemini key/model. Set `DEBUG=false`, `AUTO_CREATE_TABLES=false` and `CORS_ORIGINS=https://your-hostname`.
3. Create the login file without putting the password in shell history:

```bash
mkdir -p deploy
sudo apt-get install apache2-utils
htpasswd -cB deploy/.htpasswd presenter
chmod 644 deploy/.htpasswd
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

Caddy obtains and renews HTTPS certificates when DNS and ports are correct. nginx protects the UI, API, source images and WebSockets with the same login. The status endpoint exposes only liveness. The database and image files use persistent volumes; OCR weights use a separate cache volume. The first startup downloads models and may take several minutes. The API runs as a nonroot user and applies migrations before accepting traffic.

```bash
docker compose ps
docker compose logs --tail 100 backend
curl --fail https://your-hostname/health
```

Sign in and process a synthetic document; verify fields, source image, export and history after restarting the backend. Readiness checks verify the database and initialized models, but do not prove your Gemini credential/quota works. Do not use `docker compose down -v` on a deployment containing data.

This setup serves React and the API together, avoiding cross-origin authentication and WebSocket complications. A separately hosted Vercel UI would require an additional authentication/CORS configuration before public use.

## Import SQLite records

Choose the correct source explicitly. This workspace contains both `backend/idps.db` and a separate legacy `Database/db/idps.sqlite3`; they are different datasets. Do not import the synthetic preview database. The importer supports only the current IDPS schema and refuses incompatible legacy schemas. It leaves the original unchanged, creates a consistent backup, requires an empty migrated destination, preserves IDs and UTC timestamps, copies source images, verifies counts and resets PostgreSQL sequences. Import is all-or-nothing for database rows; copied files are removed on failure. An interrupted process can leave files that must be reviewed before retrying.

Stop API writes before importing. Mount the original SQLite file and its upload directory into a one-off backend container, read only:

```bash
docker compose stop backend web
docker compose run --rm backend alembic upgrade head
docker compose run --rm \
  -v "$PWD/backend/idps.db:/legacy/idps.db:ro" \
  -v "$PWD/backend/uploads:/legacy/uploads:ro" \
  backend python -m scripts.import_sqlite \
  --source /legacy/idps.db --source-uploads /legacy/uploads \
  --backup /app/uploads/import-check.sqlite3 --dry-run
docker compose run --rm \
  -v "$PWD/backend/idps.db:/legacy/idps.db:ro" \
  -v "$PWD/backend/uploads:/legacy/uploads:ro" \
  backend python -m scripts.import_sqlite \
  --source /legacy/idps.db --source-uploads /legacy/uploads \
  --backup /app/uploads/import-original.sqlite3
docker compose up -d backend web
```

Use the actual source upload directory if different. Each backup filename must be new. Secure and remove import backups from the uploads volume after copying them to private backup storage. Missing images abort the import rather than silently breaking source previews. SQLite dates without a timezone are interpreted as UTC; confirm that assumption for legacy data.

## Backups and recovery

Back up PostgreSQL and uploads together during a maintenance window. Keep encrypted copies outside the VM and periodically test restoration into a separate stack. These commands run on a Linux VM:

```bash
mkdir -p backups
chmod 700 backups
docker compose stop backend web
docker compose exec -T db pg_dump -U idps -d idps -Fc > backups/idps.dump
docker compose run --rm --no-deps --user root --entrypoint tar backend -czf - -C /app uploads > backups/uploads.tar.gz
docker compose start backend web
```

For restoration, stop writes, restore images into the uploads volume with ownership `10001:10001`, and restore the dump into a fresh PostgreSQL database using `pg_restore -U idps -d idps --exit-on-error`. Run migrations and compare document counts/source previews before reopening traffic. Never restore over a live database without a verified backup and an intentional recovery plan.

When transferring the current Windows database to Docker, export its `idps` database with the portable `pg_dump.exe`, restore that dump, and copy all three source images from `backend/uploads_postgres/` into `/app/uploads` in the Docker volume. Stored paths must then be adjusted for the new operating system. With API writes stopped, run:

```bash
docker compose run --rm backend python -m scripts.relocate_uploads
docker compose run --rm backend python -m scripts.relocate_uploads --apply
```

The first command validates only. The second updates paths in a single transaction after confirming every image exists within the configured upload directory. Both support original Windows path separators and report counts without document content.

## Presentation and verification

Use [the pgAdmin guide](DATABASE_PRESENTATION.md) through an SSH tunnel. It remains private on loopback. CI now starts PostgreSQL 16, checks migrations and exercises legacy import, relations, booleans and sequence continuity. Local validation and unverified deployment steps are recorded in [FOLLOW_UP.md](FOLLOW_UP.md).
