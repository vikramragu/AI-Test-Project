# Implementation Plan: AI-Powered Restaurant Recommendation System

Phase-wise build plan derived from [problemStatement.md](./problemStatement.md) and [architecture.md](./architecture.md). Each phase has a goal, tasks, deliverables, and exit criteria so progress can be checked before moving on. Phases are meant to be built roughly in order — each one depends on the previous.

## Phase 0 — Project Setup

**Goal**: A runnable skeleton with tooling in place, before any real logic is written.

- Initialize git repo, `.gitignore` (Python, `data/cache/`, `.env`).
- Create folder structure from architecture §6 (`data/`, `core/`, `api/`, `frontend/`, `tests/`).
- Set up `requirements.txt` (or `pyproject.toml`): `fastapi`, `uvicorn`, `pandas`, `datasets`, `groq`, `pydantic-settings`, `pytest`, `streamlit`.
- Add `config.py` with `pydantic-settings` `Settings` (`GROQ_API_KEY`, `LLM_MODEL`, `DATASET_NAME`, `CACHE_DIR`, `MAX_CANDIDATES_TO_LLM`, `LOG_LEVEL`) and `.env.example`.
- Verify `pytest` runs (even with zero tests) and `uvicorn api.main:app` boots an empty FastAPI app.

**Exit criteria**: Empty app boots locally; config loads from `.env`; repo structure matches architecture doc.

## Phase 1 — Data Ingestion & Preprocessing

**Goal**: The Zomato dataset is loaded, cleaned, and available as an in-memory DataFrame of canonical `Restaurant` records.

- `data/schema.py`: define the `Restaurant` record (`name, location, cuisines: list[str], cost, budget_tier, rating, extra_attributes`).
- `data/loader.py`: pull dataset from Hugging Face (`ManikaSaini/zomato-restaurant-recommendation`), cache to `data/cache/zomato.parquet`, load from cache on subsequent runs.
- `data/preprocessor.py`:
  - Normalize `location`/`city` casing.
  - Split multi-value `cuisine` strings into lists.
  - Parse `cost` to numeric; derive `budget_tier` (low/medium/high) via thresholds.
  - Coerce/validate `rating`; drop rows with unusable ratings.
  - Deduplicate restaurants.
- Manual/inspection script or notebook to eyeball the cleaned data (field distributions, null counts, cuisine value variety) — informs the exact thresholds used for `budget_tier`.

**Deliverables**: `data/loader.py`, `data/preprocessor.py`, `data/schema.py`, cached parquet file, a small `tests/test_preprocessor.py` covering normalization edge cases (missing cost, empty cuisine, duplicate rows).

**Exit criteria**: Loading the dataset end-to-end (download → cache → clean) produces a DataFrame of valid `Restaurant` records with no null ratings/cuisines; re-running uses the cache and doesn't re-download.

## Phase 2 — Filtering Engine

**Goal**: Given user preferences, deterministically produce a bounded, ranked candidate list — no LLM involved yet.

- `core/filter.py`:
  - Hard filters: location (case-insensitive), budget_tier, cuisine containment, `rating >= min_rating`.
  - Sort by `rating desc, cost asc`; truncate to top 15–20.
  - Progressive relaxation when zero matches (drop cuisine → drop budget → drop rating), tracking which constraints were relaxed.
- `tests/test_filter.py`: cases for exact match, no match (relaxation path), budget/rating boundaries, cuisine partial matches, candidate cap enforcement.

**Deliverables**: `core/filter.py` + tests, using Phase 1's cleaned dataset as fixture data.

**Exit criteria**: For a range of realistic and adversarial preference inputs (typo'd city, nonexistent cuisine, very high min rating), filtering always returns a non-empty, bounded, correctly sorted candidate list with relaxation flags where applicable.

## Phase 3 — LLM Integration (Prompting & Ranking)

**Goal**: Turn a filtered candidate list into ranked, explained recommendations via an LLM served by Groq.

- **LLM provider**: [Groq](https://groq.com) via the `groq` Python SDK (OpenAI-compatible chat completions API). Model is config-driven (`LLM_MODEL` env var, default `openai/gpt-oss-120b`); `qwen/qwen3.6-27b` is a supported alternative on the same code path. Structured output uses Groq's OpenAI-style tool/function-calling (`tools` + `tool_choice` forcing the one tool), not free-form text.
- `core/prompt_builder.py`: system prompt (role + output contract), inject candidates as compact JSON, include free-text preferences, define the tool-call JSON schema (`{ recommendations: [{ name, cuisine, rating, cost, explanation }], summary }`). System prompt explicitly instructs the model to treat free-text preferences as data, not instructions, to reduce prompt-injection risk.
- `core/llm_client.py`: `groq` SDK wrapper — request construction, tool schema attachment, timeout + retry/backoff (max 3 attempts) for retryable errors (`RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`); non-retryable errors (`AuthenticationError`, `BadRequestError`, etc.) fail immediately without retrying. Validates the response is grounded (every recommended name must match a candidate exactly) before returning it. Raises a typed `LLMError` on repeated failure, schema-invalid output, or a groundedness violation.
- `core/fallback.py`: pure-pandas weighted ranking (rating + cost) with template-generated explanations, used when the LLM path fails.
- `tests/test_prompt_builder.py`: prompt/schema construction is correct given known candidates.
- `tests/test_llm_client.py`: mocked Groq client — success path parses correctly; malformed tool-call JSON, hallucinated restaurant names, and empty recommendations each raise `LLMError`; retryable errors are retried up to the cap and non-retryable errors fail fast without retrying.
- `tests/test_fallback.py`: fallback ranking produces valid output shape without ever calling the LLM.
- Manual smoke test against the real Groq API (requires a `GROQ_API_KEY`) with a handful of realistic preference sets — check explanation quality, not just schema validity.

**Deliverables**: `core/prompt_builder.py`, `core/llm_client.py`, `core/fallback.py`, tests, a short note in the repo (or this doc) on prompt iterations if the initial prompt needs tuning.

**Exit criteria**: Given a fixed candidate list, the LLM path returns schema-valid, sensible recommendations grounded in the candidate list; forcing an LLM failure (bad API key, mocked timeout, mocked hallucination) correctly falls through to the fallback ranker without crashing.

## Phase 4 — API Layer

**Goal**: Expose the recommendation flow over HTTP.

- `api/models.py`: `UserPreferences` request schema, `RecommendationResponse` response schema (including a flag/field for "filters relaxed" and "fallback used").
- `api/main.py`: FastAPI app, CORS config, startup hook loading the dataset once into an in-memory singleton.
- `api/routes/recommendations.py`: `POST /recommendations` wiring together filter → prompt builder → LLM client → fallback-on-failure → response.
- `tests/test_api.py`: end-to-end request tests using `TestClient`, with the LLM client mocked (happy path, no-match/relaxed path, LLM-failure/fallback path, invalid request body).

**Deliverables**: Working `POST /recommendations` endpoint; OpenAPI docs available at `/docs`.

**Exit criteria**: Can `curl`/Postman a request with realistic preferences and get back a well-formed JSON response in all three flows (normal, relaxed filters, fallback ranker).

## Phase 5 — Frontend

**Goal**: A usable UI for entering preferences and viewing results, per problem statement §"Output Display".

- `frontend/app.py` (Streamlit): form for location, budget, cuisine, min rating, free-text extra preferences.
- Call the FastAPI backend; render results as cards showing name, cuisine, rating, cost, and AI-generated explanation (plus an optional summary if present).
- Show a non-blocking notice when filters were relaxed or the fallback ranker was used, so the user isn't misled into thinking it's a full LLM explanation.
- Basic loading/error states (backend unreachable, empty results).

**Deliverables**: Runnable `streamlit run frontend/app.py` pointed at the local API.

**Exit criteria**: A person can fill the form, submit, and see readable recommendation cards for several real preference combinations (including an intentionally obscure one that triggers relaxed filters or fallback).

## Phase 6 — Hardening & Non-Functional Pass

**Goal**: Address the concerns in architecture §7–8 before calling this done.

- Logging: filter parameters, candidate count, LLM latency, fallback usage — enough to diagnose "why did I get this recommendation" after the fact.
- Confirm dataset-unavailable-at-startup behavior (no cache, no network) fails with a clear error rather than hanging or crashing obscurely.
- Re-check cost controls: verify the top-15–20 cap is actually enforced before every LLM call, even after relaxation logic changes the candidate set.
- Run the full test suite (`pytest`) and fix any gaps found in earlier phases' "exit criteria."
- Light manual exploratory testing across the UI for edge cases: empty preferences, extreme budget/rating values, cuisines not present in the dataset.

**Deliverables**: Updated logging, a short "known limitations" note if anything is deliberately deferred (see Phase 7 candidates below).

**Exit criteria**: No unhandled exceptions surface to the user in any tested scenario; logs are sufficient to explain any given recommendation response after the fact.

## Phase 7 — Packaging & Docs

**Goal**: Make the project runnable by someone else with minimal guidance.

- `Dockerfile` for the API, `docker-compose.yml` wiring API + frontend containers together.
- `.env.example` kept in sync with actual required config keys.
- `README.md`: setup instructions (env vars, install, run API, run frontend), a short architecture pointer back to `docs/architecture.md`.

**Exit criteria**: `docker-compose up` (with a valid `GROQ_API_KEY` in `.env`) brings up a working system end-to-end for a fresh clone.

## Out of Scope for This Plan (see architecture §9)

Deferred unless explicitly requested later: semantic/embedding-based matching, multi-turn conversational refinement, persistence of user history/feedback, and swapping the frontend framework or LLM provider.
