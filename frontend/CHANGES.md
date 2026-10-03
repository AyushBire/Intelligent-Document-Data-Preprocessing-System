# IDPS — deployment changes

Files in this folder mirror your repo layout. **Copy them over your repo**, then apply the
small manual patches in section 2 (files I don't have a full copy of).

## 1. Files included (replace / add)

| Path | What changed |
|---|---|
| `backend/requirements.txt` | Pinned; added `aiosqlite`, `asyncpg`; torch installed separately (CPU wheel) |
| `backend/app/config.py` | Model default -> `gemini-2.5-flash`; new settings (`MAX_CONCURRENT_JOBS`, `PRELOAD_MODELS`, `AUTO_CREATE_TABLES`) |
| `backend/app/db.py` | `check_same_thread` only for SQLite (Postgres-safe), `pool_pre_ping` |
| `backend/app/models/__init__.py` | Explicitly registers all models |
| `backend/app/schemas/document.py` | `file_path` removed from API response |
| `backend/app/api/documents.py` | UUID filenames, magic-byte validation, chunked size check, PDF removed, own DB session in background task, files deleted with the record, no `__dict__` hack |
| `backend/app/api/health.py` | `/health` (liveness) + `/health/ready` (DB + models) |
| `backend/app/services/pipeline_service.py` | Concurrency limit, job TTL, model preload, generic client errors, cleanup on failure, no wasted box drawing |
| `backend/app/services/document_service.py` | PATCH now keeps child tables in sync; `delete_document` returns file path |
| `backend/processing/llm_processor.py` | Timeout + retry/backoff, default model fixed |
| `backend/main.py` | Logging configured once, preload at startup, `/docs` hidden in prod, tighter CORS |
| `backend/alembic.ini`, `alembic/env.py`, `script.py.mako` | Working async Alembic setup |
| `backend/tests/test_smoke.py`, `pytest.ini` | Smoke + upload-validation + deskew regression tests |
| `backend/Dockerfile`, `.dockerignore` | CPU torch, baked OCR weights, non-root, migrations on start |
| `frontend/Dockerfile`, `nginx.conf`, `.dockerignore` | Multi-stage build, SPA + `/api` + `/ws` proxy, basic auth, headers |
| `docker-compose.yml`, `.env.example`, `.gitignore` | Postgres + backend + web |
| `.github/workflows/ci.yml` | Backend tests, frontend lint+build, docker build |

## 2. Manual patches

### 2.1 `backend/processing/preprocessing.py`

**a) `deskew()` — make the angle correct on every OpenCV version.** Replace

```python
angle = cv2.minAreaRect(coords)[-1]

if angle < -45:
    angle = 90 + angle
```
with
```python
angle = cv2.minAreaRect(coords)[-1]

# OpenCV >= 4.5 returns (0, 90]; older versions returned [-90, 0).
# Normalise to the old convention so the logic below is version-independent.
if angle > 0:
    angle -= 90

if angle < -45:
    angle = 90 + angle
```

**b) `load_image()` — downscale huge photos (big OCR speed-up).** Add at the top of the file
`import os`, then in `load_image`, after the `None` check:

```python
max_side = int(os.getenv("OCR_MAX_SIDE_PX", "2400"))
h, w = image.shape[:2]
scale = max_side / max(h, w)
if scale < 1:
    image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
```

### 2.2 Remove duplicate logging setup
Delete the line `logging.basicConfig(level=logging.INFO)` from `processing/ocr.py`,
`processing/preprocessing.py` and `processing/pipeline.py` (logging is configured once in `main.py`).
Also replace `print("Loading EasyOCR model...")` in `ocr.py` with nothing (the logger line below it is enough).

### 2.3 `backend/app/models/document.py` — add indexes (do this BEFORE generating the migration)
```python
document_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
...
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), index=True
)
```

### 2.4 Frontend

**a) Dependencies (fixes clean-install / Docker builds):**
```bash
cd frontend
npm i axios react-router-dom @tanstack/react-query lucide-react
# delete the stray root-level package.json, package-lock.json and node_modules
```
Commit the updated `frontend/package-lock.json`.

**b) `frontend/tsconfig.app.json`** — add `"strict": true` under `compilerOptions`
(then run `npm run build` and fix anything it reports).

**c) `frontend/src/types/index.ts`** — delete `file_path: string;` from `DocumentResponse`.

**d) `frontend/src/pages/ProcessPage.tsx`**
- Add `import axios from "axios";`
- File input: `accept=".jpg,.jpeg,.png,.bmp,.tiff"`
- Text: `JPG, PNG, BMP, TIFF — max 20 MB`; remove `"PDF"` from the badge list.
- In `handleFile`, before `setStage("uploading")`:
```tsx
if (f.size > 20 * 1024 * 1024) {
  setFileName(f.name);
  setStage("error");
  setError("File is larger than 20 MB.");
  return;
}
```
- Replace the `catch` in `handleFile` with:
```tsx
} catch (e: unknown) {
  const detail = axios.isAxiosError(e) ? e.response?.data?.detail : undefined;
  setStage("error");
  setError(typeof detail === "string" ? detail : e instanceof Error ? e.message : "Upload failed");
}
```

**e) `frontend/src/pages/DatabasePage.tsx` — fix the JSON editor** (currently you can't type invalid
intermediate JSON because the textarea snaps back). Add state:
```tsx
const [structuredText, setStructuredText] = useState("");
const [jsonError, setJsonError] = useState("");
```
In `startEdit` add `setStructuredText(JSON.stringify(selectedDoc.structured_data, null, 2)); setJsonError("");`

Replace `saveEdit` with:
```tsx
const saveEdit = () => {
  if (!selectedDoc) return;
  let structured: Record<string, unknown>;
  try {
    structured = JSON.parse(structuredText);
  } catch {
    setJsonError("Extracted fields must be valid JSON.");
    return;
  }
  updateMut.mutate({ id: selectedDoc.id, data: { ...editData, structured_data: structured } });
};
```
Replace the structured-data `<textarea>` with:
```tsx
<textarea
  id="edit-structured-data"
  rows={10}
  value={structuredText}
  onChange={(e) => { setStructuredText(e.target.value); setJsonError(""); }}
  className="w-full bg-[#1c2036] border border-[#2e3250] rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 resize-none"
/>
{jsonError && <p role="alert" className="text-red-400 text-xs mt-1">{jsonError}</p>}
```

### 2.5 Repo cleanup
- Delete the legacy Streamlit `app.py`, `Database/schema.sql`, and the unused `WebSocket` code if you don't need it (the frontend polls).
- Make sure `.env` was never committed. If it was: rotate the Gemini key and purge it from git history.

## 3. First deploy

```bash
# 1. lock exact versions from your WORKING environment
pip freeze | grep -iE "easyocr|opencv|numpy|google-generativeai|fastapi|sqlalchemy"   # compare with requirements.txt

# 2. generate the initial migration (empty local SQLite DB), review it, commit it
cd backend && rm -f idps.db
GEMINI_API_KEY=x alembic revision --autogenerate -m "initial schema"
cd ..

# 3. secrets
cp .env.example .env            # fill GEMINI_API_KEY, POSTGRES_PASSWORD, CORS_ORIGINS
docker run --rm httpd:2.4-alpine htpasswd -Bbn admin 'YOUR_PASSWORD' > deploy/.htpasswd

# 4. run
docker compose up -d --build
docker compose logs -f backend  # wait for "DocumentPipeline loaded"
curl localhost/health
```
Put HTTPS in front (Caddy, a cloud load balancer, or certbot). **Do not expose basic auth over plain HTTP.**
Use a server with **>= 4 GB RAM**.

## 4. Not included (next steps)
1. Real authentication (JWT / SSO) — nginx basic auth is only a stop-gap.
2. Redis + worker (arq/RQ) so you can run multiple backend workers; until then keep `--workers 1`.
3. PII: mask Aadhaar numbers in API/UI, encrypt uploads at rest, retention/auto-delete policy.
4. PDF support (render pages with PyMuPDF) if you need it.
5. Rate limiting (`slowapi`) and structured JSON logging.
