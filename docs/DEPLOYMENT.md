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

Create **three applications** from the same repository, each with a different
*root directory*:

| Dokploy app | Root dir | Build command | Start command | Port |
|---|---|---|---|---|
| `ielts-api` | `api` | `pip install -r requirements.txt && python -m spacy download en_core_web_sm` | `uvicorn main:app --host 0.0.0.0 --port 8010` | 8010 |
| `ielts-worker` | `api` | `pip install -r requirements.txt` | `python ../worker/worker.py` | — |
| `ielts-web` | `web` | `npm install && npm run build` | `npm run start` | 3000 |

> The worker shares the `api/` code, so point its root dir at `api` and start
> `../worker/worker.py` (it adds `api/` to `sys.path`). Alternatively keep root
> at the repo and run `python worker/worker.py` after installing
> `api/requirements.txt`.

## 3. Production environment variables

**API & worker** (set in Dokploy → Environment):

```
MONGODB_URI=<atlas-uri>
MONGODB_DB=ielts_ai_mastery
JWT_SECRET=<long-random-string>
AI_PROVIDER=openai
OPENAI_API_KEY=<key>          # or ANTHROPIC_API_KEY / OLLAMA_*
UPLOAD_DIR=./storage/uploads
CORS_ORIGINS=https://your-web-domain
```

**Web**:

```
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain
```

## 4. Notes

- Set `CORS_ORIGINS` on the API to your deployed web domain.
- The API serves Swagger at `/docs`; lock it down or disable in production if
  desired.
- For persistent uploads in production, mount a volume at `api/storage/uploads`
  (or switch `UPLOAD_DIR` to a mounted path).
- Atlas **Network Access** must allow your Dokploy host's IP (or `0.0.0.0/0`).
- Run the seed script once against production:
  `python scripts/seed_ielts_data.py --email you@example.com`.
