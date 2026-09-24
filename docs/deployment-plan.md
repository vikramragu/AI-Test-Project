# Deployment Plan — Railway (backend) + Vercel (frontend)

Target topology: the FastAPI backend deploys as a Railway service; the static
`frontend/` (HTML/CSS/JS, no build step) deploys as a Vercel static site. They
are two independent deployables that talk over HTTPS — Vercel does not proxy
or build the Python code, and Railway does not serve the frontend.

```
Browser  --->  Vercel (static frontend)  --->  Railway (FastAPI backend)  --->  Groq API
                                                        |
                                                        v
                                          Hugging Face dataset (download on boot,
                                          cached to local disk)
```

This plan is deployment-specific and sits alongside `docs/implementation-plan.md`
Phase 7 (which covers local Docker packaging). Docker is optional here —
Railway can build directly from the repo via Nixpacks — but a Dockerfile is
called out below as the recommended path given a repo-specific risk (Python
3.14 pinning; see §1.2).

---

## 1. Pre-deployment changes required

These are gaps that exist because the project has only ever been run locally
by hand. None are large, but the deploy will fail or misbehave without them.
Treat this as a checklist to work through (and confirm with me) before the
first deploy attempt.

### 1.1 Backend must bind to Railway's `$PORT`, not a hardcoded port

Railway injects a `PORT` env var and routes traffic to whatever port the
process listens on. There's currently no `Procfile`/start command in the
repo. Add one of:

- `Procfile`: `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- or set the Railway service's **Start Command** directly to the same line.

### 1.2 Pin the Python version (3.14 is very new)

The local `.venv` runs **Python 3.14.7**. Railway's Nixpacks Python provider
may not yet package 3.14 (it tends to lag the newest CPython release by a few
months). Two options:

- **Safer**: add a `Dockerfile` using `python:3.12-slim` (or 3.13) as the base
  image — the code has no 3.14-only syntax, so downgrading is low-risk — and
  let Railway build from that instead of Nixpacks.
- **Riskier**: add a `.python-version` file pinning `3.14` and hope Nixpacks
  has caught up; verify by watching the first build log.

Recommendation: go with the Dockerfile. It also gives a fixed, reproducible
build environment instead of depending on what Nixpacks resolves at build
time, and doubles as the Phase 7 Docker deliverable.

### 1.3 CORS: stop allowing `*` in production

`api/main.py` currently sets `allow_origins=["*"]`. That's fine for local
dev but means any website can call the API from a browser. Add an
`allowed_origins: list[str]` (or comma-separated string) setting to
`config.py`, default to `["*"]` for local dev, and set it to the exact Vercel
URL(s) (e.g. `https://bangalore-bites.vercel.app`) via a Railway env var in
production. This is a small, low-risk code change — worth doing before going
live since the API has no auth of its own.

### 1.4 Dataset cold-start cost

`load_restaurants()` runs in the FastAPI `lifespan` hook — on a cold boot
with no cache, it downloads and preprocesses the full Hugging Face dataset
(51,717 raw rows) before the server can accept traffic. On Railway:

- Railway's disk is **ephemeral across deploys** (a new deploy = a fresh
  filesystem), so every deploy re-triggers a full download+preprocess unless
  addressed.
- A slow cold start risks Railway's healthcheck timing out and marking the
  deploy unhealthy.

Recommended fix: bake the *clean* parquet cache into the Docker image at
build time, so it ships with the image and boot never touches the network:

```dockerfile
RUN python -c "from data.loader import load_restaurants; load_restaurants()"
```

This runs during `docker build`, not at container start, so the resulting
image already contains `data/cache/zomato_clean.parquet` and boot is
instant. (Alternative: a Railway Volume mounted at `data/cache` — persists
across restarts but adds infra to manage for no real benefit here, since the
dataset is static and small.)

### 1.5 Point the frontend at the Railway backend URL — via a Vercel env var

`frontend/app.js` reads `window.API_BASE_URL || "http://localhost:8000"`.
Rather than hardcoding the Railway URL into committed HTML, Vercel's Build
Command (available even for a plain static site under Framework Preset
"Other") generates a small `config.js` from an env var at build time:

- `frontend/config.js` is committed as a no-op placeholder (so local dev is
  unaffected — `app.js`'s own `localhost:8000` fallback still applies).
- `frontend/index.html` loads it right before `app.js`:
  `<script src="config.js"></script>`
- Vercel project settings:
  - Root Directory: `frontend`
  - Build Command: `echo "window.API_BASE_URL = \"$VITE_API_BASE_URL\";" > config.js`
  - Output Directory: `.`
  - Env var: `VITE_API_BASE_URL` = `https://<railway-host>` (no trailing slash)

This keeps the backend URL out of git entirely and makes changing it a
dashboard edit + redeploy, no code change.

### 1.6 Secrets

`GROQ_API_KEY` must be set as a Railway **environment variable** in the
dashboard, never committed. `.env` stays local-only (already gitignored).

### Summary of file changes needed

| File | Change | Why |
|---|---|---|
| `Procfile` (new) | `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT` | Railway needs a start command |
| `Dockerfile` (new) | Python 3.12-slim base, install deps, bake dataset cache | avoid version-support risk + cold-start downloads |
| `config.py` | add `allowed_origins` setting | remove `allow_origins=["*"]` in prod |
| `api/main.py` | read `allowed_origins` from settings instead of hardcoded `["*"]` | same |
| `frontend/config.js` (new) | no-op placeholder, overwritten by Vercel's build command | point static frontend at deployed backend without committing the URL |
| `frontend/index.html` | load `config.js` before `app.js` | same |
| `.env.example` | document `ALLOWED_ORIGINS` | keep in sync per project convention |

Say the word and I can implement 1.1–1.6 directly; this plan intentionally
stops at the plan/checklist stage since deployment config wasn't part of the
original ask.

---

## 2. Deploying the backend to Railway

1. Push the repo to GitHub if not already (it already has a remote:
   `git@github.com:vikramragu/AI-Test-Project.git` — confirm `main` is
   pushed and up to date).
2. In Railway: **New Project → Deploy from GitHub repo** → select this repo.
3. If a `Dockerfile` exists at the repo root, Railway auto-detects and
   builds it. Otherwise Railway falls back to Nixpacks (see §1.2 risk).
4. Set environment variables on the Railway service (Settings → Variables):
   - `GROQ_API_KEY` (required — the real key)
   - `LLM_MODEL` = `openai/gpt-oss-120b`
   - `DATASET_NAME` = `ManikaSaini/zomato-restaurant-recommendation`
   - `CACHE_DIR` = `data/cache`
   - `MAX_CANDIDATES_TO_LLM` = `20`
   - `LOG_LEVEL` = `INFO`
   - `LLM_REQUESTS_PER_MINUTE` / `_PER_DAY`, `LLM_TOKENS_PER_MINUTE` /
     `_PER_DAY`, `LLM_RATE_LIMIT_MAX_WAIT_SECONDS` — copy from `.env.example`
   - `ALLOWED_ORIGINS` = the Vercel frontend URL, once §1.3 is implemented
5. Deploy. Railway assigns a public URL like
   `https://<service>.up.railway.app`.
6. Set the healthcheck path to `/health` in Railway's service settings so
   Railway can tell if the container is actually serving traffic (it already
   returns `{"status": "ok"}`).
7. Confirm boot logs show the dataset load line and no
   `DatasetUnavailableError`, and that `GET /health` returns 200.

---

## 3. Deploying the frontend to Vercel

Since `frontend/` is static HTML/CSS/JS with no build step:

1. In Vercel: **New Project → Import Git Repository** → same repo.
2. Set the project's **Root Directory** to `frontend/`.
3. Framework preset: **Other**.
4. Build Command: `echo "window.API_BASE_URL = \"$VITE_API_BASE_URL\";" > config.js`
5. Output Directory: `.`
6. Environment Variable: `VITE_API_BASE_URL` = the Railway URL from step 2
   above (no trailing slash).
7. Deploy. Vercel assigns a URL like `https://<project>.vercel.app`.
8. Once you know this URL, go back to Railway and set `ALLOWED_ORIGINS` to
   it (§1.3).

---

## 4. Post-deploy verification checklist

- [ ] `GET https://<railway-url>/health` → `{"status": "ok"}`
- [ ] Open the Vercel URL in a browser, submit a real search (e.g. location
      "Koramangala") — confirm recommendations render, not a CORS error in
      devtools console
- [ ] Trigger the fallback path (e.g. by temporarily setting a bad
      `GROQ_API_KEY` in Railway) and confirm the UI still returns results
      with `source: "fallback"` rather than erroring
- [ ] Trigger the no-match path (nonexistent location) and confirm the UI
      shows the "not found" state, not a crash
- [ ] Check Railway logs for the `request_id`-tagged log lines to confirm
      logging survived the move to a hosted environment

---

## 5. Known limitations of this deployment topology

- **Single-instance state**: the client-side rate limiter
  (`core/rate_limiter.py`) and the in-memory dataset (`app.state`) live in
  one process's memory. If Railway ever scales this service to multiple
  replicas, each replica tracks its own rate-limit budget independently —
  the *effective* combined rate limit against Groq becomes
  `replicas × configured limit`, which could exceed Groq's real account
  limits. Fine at 1 replica (the default); revisit before scaling out.
- **Cold starts on redeploy**: every new deploy is a fresh container. With
  §1.4's baked-in cache this is fast; without it, every deploy re-downloads
  the dataset.
- **No persistence**: nothing about a user's search is stored anywhere
  (by design, per the existing architecture) — nothing new here, just
  restating that this remains true after deployment.
- **CORS is currently wide open** until §1.3 is implemented — noted above
  as a pre-deploy action item, not yet done.

---

## 6. Rollback

Both Railway and Vercel keep prior deploys and support one-click rollback to
a previous successful deploy from their respective dashboards. No database
migrations exist in this project, so a rollback on either side is safe and
has no cross-service ordering requirement.
