# Vercel frontend deployment

The website is https://intelligent-document-data-preproces.vercel.app/signin.
The frontend project uses root directory `frontend`, Vite, `npm run build`, and
output directory `dist`.

`frontend/vercel.json` routes `/api/:path*` to
`https://idps-backend.vercel.app/api/:path*` and `/health` to the hosted API.
The remaining application routes use the React SPA fallback. API responses are
private and not cached. Browser requests and image URLs stay on the frontend
origin so the HttpOnly authentication cookie works without cross-site cookies.

The FastAPI project `idps-backend` uses root directory `backend`, the FastAPI
preset, and a Singapore function region. It connects to the Neon Free PostgreSQL
database. Neither project requires a laptop tunnel.

Sign in through `/signin`; the browser login popup is no longer used. Admin and
Gemini credentials and the cloud database URL are private backend environment
variables. They must never be embedded in frontend code or committed to Git.

See [VERCEL_BACKEND.md](VERCEL_BACKEND.md) for migration, processing, storage and
runtime settings. To verify a deployment, check login, upload a synthetic image,
review its extracted fields and source image, and confirm logout revokes access.
