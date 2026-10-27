# Running the hosted IDPS project

Open https://intelligent-document-data-preproces.vercel.app/signin and sign in
with the existing admin credentials. The frontend and backend are hosted on
Vercel; PostgreSQL is hosted on the Neon Free plan in Singapore.

No laptop backend, PostgreSQL server, tunnel, or open PowerShell terminal is
required. The laptop can be switched off while the website is used elsewhere.
The `start-backend.ps1` launcher recognizes the hosted connection and preserves it
rather than replacing it with a temporary tunnel.

## Presentation workflow

1. Open the website and sign in.
2. Upload a clear JPG, PNG, BMP or TIFF image up to 4 MB. PDF is not supported.
3. Wait for extraction to finish, then review the fields, report and source image.
4. Export or edit the result as needed, and sign out when finished.

The cloud mode sends document images to Gemini for transcription and extraction.
Normalized private source images, extracted records, sessions and job status are
stored in PostgreSQL. Existing local records have not been migrated. Use
synthetic documents for public demonstrations.

Vercel Hobby and Neon Free quotas apply, together with the existing Gemini API
quota. No payment card or paid plan was added during deployment. First access
after inactivity can take longer while services wake up.

## Local development

Local OCR remains available through the existing backend commands and
`backend/requirements-local.txt`. The public frontend continues to use the cloud
backend unless its proxy configuration is explicitly changed. See
[VERCEL_BACKEND.md](VERCEL_BACKEND.md) for cloud configuration and
[DEPLOYMENT.md](DEPLOYMENT.md) for the independent Docker deployment.
