# IELTS AI Mastery Engine

A complete, local-first IELTS preparation engine. It imports your sources
(PDF, DOCX, TXT, CSV, JSON, URLs, pasted text), extracts and **ranks** the
highest-value vocabulary, collocations and sentence patterns, enriches them
with AI (meaning, Persian translation, examples, mistakes), and trains you with
**SM-2 spaced repetition** flashcards, quizzes, daily plans and progress
tracking.

```
ielts-ai-mastery/
├── web/      Next.js 14 + TypeScript + Tailwind (shadcn-style UI)  → http://localhost:3000
├── api/      FastAPI backend (auth, ingestion, extraction, AI, study) → http://localhost:8010
│          (processing runs in the API via FastAPI BackgroundTasks — no worker)
├── scripts/  Seed script + curated starter dataset (231 words / 109 phrases / 52 patterns)
├── shared/   Cross-service constants (sections, categories, statuses)
└── docs/     MongoDB Atlas + Dokploy deployment notes
```

No Docker required. Runs on macOS with simple commands.

---

## Architecture at a glance

- **Backend (`api/`)** — modular FastAPI service: `auth/`, `sources/`,
  `ingestion/`, `extraction/`, `ai/`, `content/`, `study/`, `progress/`,
  `jobs/`, `utils/`. Async MongoDB via Motor.
- **Extraction** — dependency-light, deterministic. Cleans → tokenises →
  lemmatises (spaCy, with a regex fallback if the model isn't installed) →
  n-gram & collocation extraction → IELTS section classification → 0–100
  **priority scoring**.
- **AI layer (`api/ai/`)** — provider abstraction (`openai | anthropic |
  ollama`). The app works with **only one** provider configured, and degrades
  gracefully (no AI = extraction still works, just without translations).
- **Jobs** — every import creates a job in MongoDB and is processed via a
  **FastAPI BackgroundTask** in the same API process (status: `pending →
  processing → done | failed`). No separate worker process is needed.
- **Study** — simplified SM-2; cards move `new → learning → review → mastered`.

### Storage architecture (production-grade, deployment-safe)

- **MongoDB Atlas is the source of truth for all structured text & data**:
  users, sources, raw + cleaned text, `source_chunks`, vocabulary, phrases,
  sentence patterns, AI explanations/Persian meanings/examples, learning cards,
  review history, daily plans, progress, processing jobs + logs.
- **Amazon S3 stores all original/binary files** (PDF, DOCX, TXT, CSV, JSON,
  future images/audio/exports). Mongo keeps only the S3 object **key + metadata**
  — never the binary.
- **No permanent local storage.** Uploads stream straight to S3; parsing happens
  in memory. `UPLOAD_DIR` is only a transient temp/dev-fallback dir and is safe
  to wipe. The app runs fine after deleting `api/storage/` and needs **no
  persistent volume** in deployment.
- **Seed data is embedded** in `scripts/seed_dataset.py` (Python constants) — no
  runtime dependency on `scripts/data`.
- If AWS vars are unset, a local fallback under `UPLOAD_DIR` is used so dev still
  works; configure S3 for production.

Upload flow: receive file → upload original to S3 → parse bytes in memory →
store raw/cleaned text + chunks + extraction results in Mongo. Downloads use a
short-lived **presigned URL** from `GET /sources/{id}/download-url`.

---

## 1. Prerequisites

- **Python 3.11 or 3.12 recommended.** It also runs on 3.13/3.14 using the
  core deps only (the optional NLP extras below have no wheels for 3.13/3.14
  yet — the app falls back automatically, so this is fine).
- Node.js 18+ (tested on 20/22)
- A free **MongoDB Atlas** cluster (see `docs/MONGODB_ATLAS.md`)
- *(Optional)* an OpenAI or Anthropic API key, or a local Ollama install
- **Tesseract OCR** — needed to read scanned / image-based PDFs. Without it,
  embedded-text PDFs still work and scanned PDFs fail gracefully with a warning.

  ```bash
  # macOS
  brew install tesseract
  # Ubuntu / Debian
  sudo apt-get install -y tesseract-ocr
  ```

> Check your version with `python3 --version`. If you have 3.14 and want the
> optional spaCy/pandas extras, install Python 3.12 (e.g. `brew install python@3.12`)
> and create the venv with `python3.12 -m venv .venv`.

---

## 2. Backend setup

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt          # core deps — installs on any 3.11–3.14

cp .env.example .env                      # then edit .env (see below)
```

**Optional (better extraction quality, Python ≤ 3.12 only):**

```bash
pip install -r requirements-nlp.txt
python -m spacy download en_core_web_sm
```

Without these, extraction still works using a built-in regex
tokenizer/lemmatizer, and CSV parsing uses the standard library.

### Configure `api/.env`

| Variable | What to put there |
|---|---|
| `MONGODB_URI` | **Your MongoDB Atlas connection string** (Atlas → Connect → Drivers). |
| `MONGODB_DB` | Database name (default `ielts_ai_mastery`). |
| `JWT_SECRET` | Any long random string. |
| `AI_PROVIDER` | `openai`, `anthropic`, or `ollama`. |
| `OPENAI_API_KEY` | **Your OpenAI key** (if `AI_PROVIDER=openai`). |
| `ANTHROPIC_API_KEY` | **Your Anthropic key** (if `AI_PROVIDER=anthropic`). |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | For local models (no key needed). |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | **Your S3 credentials** (original files go here). |
| `AWS_REGION` / `AWS_S3_BUCKET` | S3 region + bucket name. |
| `AWS_S3_PUBLIC_BASE_URL` | Optional CloudFront/CDN base for object URLs. |

> The app runs fine with **no** AI key — you simply won't get auto
> translations/examples until you add a key and click "Regenerate".

### Start the backend

```bash
cd api
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8010
```

> Use `python -m uvicorn` (not just `uvicorn`). If you have a Homebrew-installed
> `uvicorn` on your PATH, the bare command can run under the wrong Python and
> fail with `ModuleNotFoundError: No module named 'motor'`. Running it as a
> module always uses the venv's interpreter and packages.

API docs: http://localhost:8010/docs · Health: http://localhost:8010/health

---

## 3. Seed the starter IELTS dataset

From the repo root, with the **api venv activated** (so deps + `.env` load):

```bash
python scripts/seed_ielts_data.py --email you@example.com --reset
```

This creates the user (if new, default password `changeme123`), inserts
**231 academic words, 109 phrases, 52 sentence patterns** (Persian meanings +
English explanations + examples), and builds 70 starter flashcards. Log in with
that email to see everything immediately.

---

## 4. Frontend setup

```bash
cd web
npm install
cp .env.example .env.local      # NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
npm run dev
```

Open http://localhost:3000, register or log in (use the seeded email).

---

## 5. End-to-end test flow

1. **Start** MongoDB Atlas access, then `uvicorn` (8010) and `npm run dev` (3000).
2. **Register / log in** at http://localhost:3000.
3. *(Optional)* run the **seed script** and log in with that email — the
   Dashboard now shows totals and "cards due today".
4. **Import** a source: Import Center → paste a reading passage (or upload a
   PDF/DOCX, or add a URL) → watch the status go `pending → processing → done`
   and open **Logs** to see extraction steps.
5. **Vocabulary Ranker** → filter/sort by priority; open a word to see Persian
   meaning, collocations, examples; click **Regenerate** (needs an AI key) or
   **Add to study**.
6. **Study Mode** → reveal with `Space`, grade with `1–4`; the SM-2 scheduler
   sets the next review.
7. **Quiz** → pick a mode and answer 10 questions.
8. **Daily Plan** → top 30 words / 15 phrases / 10 patterns + due cards + ETA.
9. **Progress** → review activity, accuracy, card-status pie, source coverage.
10. **Settings** → change AI provider, target band, exam date, focus modules.

---

## Service ports

| Service | Port | Command |
|---|---|---|
| Frontend (Next.js) | 3000 | `cd web && npm run dev` |
| Backend (FastAPI) | 8010 | `cd api && python -m uvicorn main:app --reload --port 8010` |

---

## Deployment (Dokploy)

See **`docs/DEPLOYMENT.md`** for pushing to GitHub and deploying `web` and
`api` as two separate Dokploy services.

## Data quality features

Stopword filtering · lemma/duplicate merging · per-source frequency tracking ·
phrase confidence scoring · minimum frequency thresholds · manual
hide/delete/mark-important · regenerate AI explanation · reprocess source ·
paginated tables with search & filters.
