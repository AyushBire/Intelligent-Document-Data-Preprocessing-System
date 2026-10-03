# PostgreSQL deployment and presentation

Use PostgreSQL for the deployed IDPS database and pgAdmin as its visual administration interface. The existing FastAPI backend already uses SQLAlchemy, Alembic and the asyncpg driver; the production Compose stack already defines PostgreSQL. The optional pgAdmin container follows the [official container deployment documentation](https://www.pgadmin.org/docs/pgadmin4/9.17/container_deployment.html).

## Start the presentation environment

Docker Desktop with Compose is required. It was unavailable on the development machine when this configuration was prepared, so the container startup remains unverified.

1. Keep your existing `.env` credentials. Add `POSTGRES_PASSWORD`, `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` using `.env.example` as the reference. Use distinct passwords for PostgreSQL and pgAdmin.
2. Create `deploy/.htpasswd` as described in the root README.
3. From the repository root run:

```powershell
docker compose -f docker-compose.yml -f docker-compose.presentation.yml up -d --build
```

4. Open the application at `http://localhost:8080` and pgAdmin at `http://localhost:5050`.
5. Sign in to pgAdmin using `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD`.
6. Expand **IDPS Workspace → IDPS PostgreSQL**. When asked for the database password, enter `POSTGRES_PASSWORD`. The server definition is preconfigured, but contains no password.
7. Expand **Databases → idps → Schemas → public → Tables**.

Both interfaces bind to the deployment host's loopback address. On a remote server, reach pgAdmin through an SSH tunnel, such as `ssh -L 5050:127.0.0.1:5050 user@server`. Open `http://localhost:5050` on your own computer after establishing the tunnel. Use the normal HTTPS application deployment for your audience; the admin interface is for the presenter.

Normal deployment remains `docker compose up -d --build`; the pgAdmin service is included only when the presentation override file is supplied. To stop only the viewer:

```powershell
docker compose -f docker-compose.yml -f docker-compose.presentation.yml stop pgadmin
```

## Five-minute demonstration

Use synthetic invoices and receipts so the projected screen contains demonstration data.

| Step | Show | Explain |
| --- | --- | --- |
| 1 | IDPS architecture | React → FastAPI → OCR/Gemini → PostgreSQL; source images live in persistent file storage |
| 2 | Tables in pgAdmin | The shared `documents` table, document-specific child tables, and `document_confirmations` |
| 3 | Process a synthetic invoice in IDPS | The uploaded image becomes OCR text, extracted fields and a summary |
| 4 | Refresh `documents` in pgAdmin | A successfully processed document is persisted and available after page reload |
| 5 | Query Tool | Show type counts, extracted JSON and foreign-key relationships |

The current development API also uses PostgreSQL. Its portable Windows instance is separate from Docker's database volume, which starts empty unless an existing volume is reused. Use [the deployment guide](DEPLOYMENT.md) to import SQLite into an empty Docker database, or export/restore the current PostgreSQL data and its images. Synthetic preview records are excluded from the active database.

## Read-only demonstration queries

Open Query Tool on the `idps` database. Execute this script to inspect data without changing it:

```sql
BEGIN TRANSACTION READ ONLY;

SELECT id, filename, document_type, created_at
FROM documents
ORDER BY created_at DESC, id DESC
LIMIT 10;

SELECT document_type, COUNT(*) AS document_count
FROM documents
GROUP BY document_type
ORDER BY document_count DESC, document_type;

SELECT d.id, d.filename, i.invoice_number
FROM documents AS d
JOIN invoices AS i ON i.document_id = d.id
ORDER BY d.id DESC
LIMIT 10;

SELECT id, jsonb_pretty(raw_json::jsonb) AS extracted_fields
FROM documents
ORDER BY id DESC
LIMIT 3;

COMMIT;
```

To show the ER diagram, use pgAdmin's ERD Tool for the database or schema. The foreign keys connect `documents` to its child tables and confirmations. The diagram reflects the actual current schema; it does not imply application authentication or an audit feature that has not been implemented.

## How to explain the choice

“IDPS combines relational metadata with variable extracted document fields. PostgreSQL fits our relationships, transactions and reporting queries, and supports native JSONB when we need indexed field searches. Our existing backend already targets PostgreSQL, which reduces migration risk. pgAdmin makes the persisted data and schema easy to inspect during the demonstration.”

Today `raw_json` is a text column. The query above casts it to JSONB for display; it does not convert the stored column. A future reviewed migration can introduce a JSONB column when field-level querying is required.

## Remaining deployment work

Run the Compose stack, PostgreSQL migrations and a real synthetic-document extraction in the target environment. Configure HTTPS and backups. The application still requires one backend worker because its job store is in memory. If you choose a cloud provider with managed PostgreSQL, adapt the database connection and use a desktop or local pgAdmin connection instead of assuming this local Compose configuration is the final cloud deployment.
