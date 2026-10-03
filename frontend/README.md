# IDPS frontend

The supported UI lives entirely in this directory. Use Node.js 22 and run `npm ci`, then `npm run dev`. The backend must be available at `http://localhost:8000`.

| Route | Purpose |
| --- | --- |
| `/` | Dashboard with real statistics and recent documents |
| `/extract` | Selection, image preview and resumable processing |
| `/documents` | Searchable, filtered, paginated document library |
| `/documents/:id` | Result review, edits, source preview and exports |

Legacy `/process` and `/database?id=...` URLs redirect. Run `npm run lint` and `npm run build` before delivery. See the root README for environment setup, Docker authentication and deployment limitations.
