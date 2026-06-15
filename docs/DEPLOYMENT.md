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
| `ielts-api` | `api` | `pip install -r requirements.txt` | `python -m uvicorn main:app --host 0.0.0.0 --port 8010` | 8010 |
| `ielts-web` | `web` | `npm install && npm run build` | `npm run start` | 3000 |

> **No worker service.** Source processing runs inside the API via FastAPI
> BackgroundTasks, so only `api` and `web` are deployed. The `worker/` folder is
> optional and reserved for possible future heavy/batch processing — do not
> deploy it.

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
```

**Web**:

```
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain
```

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
