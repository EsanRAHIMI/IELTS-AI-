# Deployment (GitHub + Dokploy)

The project is structured so each service deploys independently. No Docker is
required, but Dokploy can build each folder with Nixpacks/Buildpacks.

## 1. Push to GitHub

```bash
cd ielts-ai-mastery   # the project root
git init
git add .
git commit -m "IELTS AI Mastery Engine"
git branch -M main
git remote add origin git@github.com:<you>/ielts-ai-mastery.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `.venv`, `node_modules`, `.next` and
uploaded files.

## 2. Recommended Dokploy service mapping

Create **two applications** from the same repository, each with a different
*root directory*:

| Dokploy app | Root dir | Build command | Start command | Port |
|---|---|---|---|---|
| `ielts-api` | `api` | `pip install -r requirements.txt` | `sh start.sh` (or `python -m uvicorn main:app --host 0.0.0.0 --port 8010`) | **8010** |
| `ielts-web` | `web` | `npm install && npm run build` | `npm run start` | **3000** |

`api/nixpacks.toml` installs **tesseract-ocr** via apt; Nixpacks auto-runs
`pip install -r requirements.txt` for Python. Do **not** override the install
phase with bare `pip` — Nixpacks puts pip in a venv and bare `pip` fails with
`command not found`.

> **No worker service.** Source processing runs inside the API via FastAPI
> BackgroundTasks, so only `api` and `web` are deployed.

## 3. Production environment variables

**API** (set in Dokploy → Environment):

```
MONGODB_URI=<atlas-uri>
MONGODB_DB=ielts_ai_mastery
JWT_SECRET=<long-random-string>
AI_PROVIDER=openai
OPENAI_API_KEY=<key>          # or ANTHROPIC_API_KEY / OLLAMA_*
# Amazon S3 (original/binary file storage)
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_REGION=eu-central-1
AWS_S3_BUCKET=<bucket>
AWS_S3_PUBLIC_BASE_URL=<optional-cloudfront-url>
UPLOAD_DIR=/tmp/ielts          # transient parsing only; NOT persistent
CORS_ORIGINS=https://your-web-domain
API_ROOT_PREFIX=/api
PORT=8010
```

> No comments (`# ...`) in Dokploy env — paste only `KEY=value` lines.  
> Set `AI_PROVIDER` once (duplicate keys leave only the last value).  
> No trailing slash on `CORS_ORIGINS` (use `https://ielts.najahai.com`, not `...com/`).  
> **`API_ROOT_PREFIX=/api`** is required when Traefik forwards `/api/*` to the container
> **without** stripping the prefix (the usual Dokploy path setup).

**Web**:

```
NEXT_PUBLIC_API_BASE_URL=https://your-web-domain/api
```

## 3b. Same-domain routing (`/api` path) — Dokploy domains

When web and API share one host (e.g. `ielts.najahai.com`), add **two domains** in Dokploy:

| Service | Host | Path | Strip path | Container port | HTTPS |
|---|---|---|---|---|---|
| `ielts-web` | `ielts.najahai.com` | `/` (empty) | off | **3000** | on |
| `ielts-api` | `ielts.najahai.com` | `/api` | off | **8010** | on |

- Set **`API_ROOT_PREFIX=/api`** on the API service so routes match `/api/auth/login`, etc.
- **Container port** must match what uvicorn listens on (8010, or `$PORT` if set in env).
- Strip path is **not** required when `API_ROOT_PREFIX` is set.

Quick check after deploy:

```bash
curl -s https://ielts.najahai.com/api/health
# {"status":"ok","db":true,...}
```

A **502 Bad Gateway** on `/api/*` almost always means the API container is down or the domain’s **container port** is wrong — open the API app → **Logs** in Dokploy first.

### Troubleshooting: 404 on login, 405 on `/api/health`

If API logs show `POST /api/auth/login` → 404, the container receives the `/api` prefix.
Set **`API_ROOT_PREFIX=/api`** in the API environment and redeploy.

## 4. Storage notes (important)

- **No persistent local volume is required.** Original files are stored in
  **Amazon S3**; all structured text/data lives in **MongoDB Atlas**. `UPLOAD_DIR`
  is used only for transient, in-process parsing and can point at `/tmp`.
- Configure the `AWS_*` vars on `ielts-api` (it uploads originals to S3 and
  pulls bytes back when extracting — all within the BackgroundTask).
- Ensure the S3 bucket's IAM user has `s3:PutObject`, `s3:GetObject` and
  `s3:DeleteObject` on the bucket. Optionally front it with CloudFront and set
  `AWS_S3_PUBLIC_BASE_URL`.
- If you previously ran with local uploads, run the one-off migration:
  `python scripts/migrate_local_storage_to_s3.py --delete-local`.

## 5. Notes

- Set `CORS_ORIGINS` on the API to your deployed web domain.
- The API serves Swagger at `/docs`; lock it down or disable in production if
  desired.
- Atlas **Network Access** must allow your Dokploy host's IP (or `0.0.0.0/0`).
- Run the seed script once against production:
  `python scripts/seed_ielts_data.py --email you@example.com`.
