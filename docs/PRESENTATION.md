# Temporary presentation deployment

The Vercel frontend connects through a Cloudflare Quick Tunnel to FastAPI on this laptop. PostgreSQL and source images remain local. A username/password gate protects document reads, uploads, edits, deletion and WebSockets. The public health route exposes only liveness. There is no cloud VM or payment card required; Gemini's own API quota/billing is separate.

## Current session

The laptop, PostgreSQL, FastAPI and tunnel must remain running with internet access. Prevent sleep during the presentation. Open `https://intelligent-document-data-preproces.vercel.app/signin`, enter the credentials from the ignored `.validation/presentation-login.txt`, then open the Vercel homepage. Authentication uses a dedicated sign-in form and an HttpOnly session cookie. Passwords are not embedded in the frontend bundle or proxy configuration.

Use synthetic documents when presenting. Temporary tunnel addresses change on restart and have no uptime guarantee. Stopping the tunnel disconnects the deployed app from the backend. This is a demonstration setup, not an unattended production service.

## Start again after reboot

Use separate PowerShell terminals. From the repository root, start PostgreSQL if it is not already running:

```powershell
& '.validation/pg-runtime/pgsql/bin/pg_ctl.exe' -D '.validation/postgres-data' -l '.validation/postgres.log' -o '-h 127.0.0.1 -p 55432' start
```

Start the backend from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The ignored root `.env` must contain `PRESENTATION_AUTH_ENABLED=true`, `PRESENTATION_USERNAME` and a strong `PRESENTATION_PASSWORD`. Keep the API on loopback. Do not start an unprotected backend through this tunnel.

Start the tunnel from the repository root and keep the terminal open:

```powershell
.validation\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate --protocol http2 --logfile .validation/tunnel.log
```

Copy the new HTTPS origin printed by cloudflared. In a fourth terminal, update the proxy and redeploy:

```powershell
.venv\Scripts\python.exe scripts/connect_presentation.py https://YOUR-NEW-ADDRESS.trycloudflare.com
git add frontend/vercel.json
git commit -m "Connect presentation backend tunnel"
git push origin main
```

The helper checks that anonymous API access receives HTTP 401 and authenticated readiness passes before changing the proxy. Vercel redeploys automatically from GitHub. Wait for the production deployment to become Ready, sign in at `/signin`, and test the dashboard and a synthetic extraction. The local Vite development server is not required for the Vercel presentation.

## End the presentation

Press Ctrl+C in the cloudflared terminal first, then in the backend terminal. The PostgreSQL database can remain local or be stopped with `pg_ctl ... stop`. Keep the database and image folders for the next presentation. No documents are deleted when these processes stop.

Browser access uses the dedicated `/signin` page. Use the existing credentials in the ignored `.validation/presentation-login.txt` file. Sessions last eight hours or until backend restart. Sign out revokes the session. Credentials are never stored in browser local storage. Keep the backend and tunnel running for the presentation.
