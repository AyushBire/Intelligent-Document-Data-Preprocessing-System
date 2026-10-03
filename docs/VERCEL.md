# Vercel frontend deployment

The Vercel project must use `frontend` as its Root Directory, the Vite preset, `npm run build` and `dist` output. `frontend/vercel.json` enables direct navigation to React routes and keeps API/health paths out of the SPA fallback.

The current FastAPI/EasyOCR backend requires persistent image storage, a PostgreSQL connection and a single process for its in-memory extraction jobs. The supported deployment for it is the Docker VM setup in [DEPLOYMENT.md](DEPLOYMENT.md). Deploying the static frontend alone does not provide extraction or database access. Vercel cannot reach the development machine's `localhost:8000`.

## Connect a hosted backend

Once the backend has a public HTTPS hostname, add these entries **before** the SPA rewrite in `frontend/vercel.json`, replacing the example hostname with the actual deployed backend:

```json
{ "source": "/api/:path*", "destination": "https://your-backend-host/api/:path*" },
{ "source": "/health", "destination": "https://your-backend-host/health" }
```

The React client polls job status over HTTP, so it does not need a WebSocket proxy. These rewrites keep API calls and source-image URLs on the frontend origin. Never put Gemini keys, PostgreSQL passwords or a shared backend password into frontend variables or proxy URLs.

The backend must retain access controls. With the existing nginx Basic Authentication gate, sign into the backend API through the Vercel-origin `/api/documents/stats` endpoint before opening the dashboard; verify that API requests and image previews carry authentication. Do not disable the backend login to work around connection errors. If using application authentication later, configure it explicitly and test the full session flow.

## Deploy and verify

1. Sign into Vercel and import the GitHub repository.
2. Set Root Directory to `frontend` and select Vite.
3. Deploy after configuring and verifying the hosted backend rewrites.
4. Check dashboard statistics, direct `/extract` navigation, a synthetic upload, processing progress, history and source-image previews.
5. Confirm an unauthenticated API request cannot read documents.

Keep all database data, upload files and Gemini credentials on the backend host. The Vercel project only needs frontend source/build files. A frontend deployment can be created before backend hosting, but it must be reported as incomplete until the end-to-end checks pass.
