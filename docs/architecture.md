# Architecture: AI-Powered Restaurant Recommendation System

This document defines the technical architecture for the system described in [problemStatement.md](./problemStatement.md). It covers the tech stack, component design, data flow, folder structure, and key engineering decisions needed to implement the Zomato-inspired recommendation service.

## 1. Goals & Constraints Recap

- Combine a **structured dataset** (Zomato restaurants from Hugging Face) with an **LLM** to produce ranked, explained recommendations.
- Inputs: location, budget, cuisine, minimum rating, free-text preferences (e.g., "family-friendly", "quick service").
- Outputs: ranked restaurants with name, cuisine, rating, cost, and an AI-generated explanation.
- Must control LLM cost/latency by pre-filtering with pandas before anything reaches the model, and must degrade gracefully if the LLM call fails.

## 2. High-Level Architecture

```mermaid
flowchart TD
    subgraph Client
        UI[Web UI / Streamlit App]
    end

    subgraph API["Backend API (FastAPI)"]
        EP["/recommendations endpoint"]
        VAL[Request Validation<br/>Pydantic Models]
    end

    subgraph Core["Recommendation Core"]
        FILTER[Filtering Engine<br/>pandas]
        PROMPT[Prompt Builder]
        LLM[LLM Client<br/>Groq API]
        PARSE[Response Parser<br/>structured JSON]
        FALLBACK[Fallback Ranker<br/>non-LLM]
    end

    subgraph Data["Data Layer"]
        LOADER[Dataset Loader<br/>HF datasets]
        CACHE[(Local Cache<br/>parquet/csv)]
        SCHEMA[Preprocessed<br/>Restaurant Records]
    end

    UI -->|user preferences| EP
    EP --> VAL --> FILTER
    LOADER --> CACHE --> SCHEMA --> FILTER
    FILTER -->|top-N candidates| PROMPT --> LLM --> PARSE --> EP
    LLM -.on failure.-> FALLBACK --> EP
    EP -->|ranked results| UI
```

## 3. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Best support for `datasets` (Hugging Face), `pandas`, and LLM SDKs |
| Backend API | FastAPI | Async, typed via Pydantic, easy to test and containerize |
| Data ingestion | `datasets` (Hugging Face) + `pandas` | Native HF dataset loading; pandas for filtering/aggregation |
| LLM | Groq (`openai/gpt-oss-120b`, alt. `qwen/qwen3.6-27b`) via `groq` SDK | Low-latency, low-cost inference; OpenAI-compatible tool/function-calling for structured JSON output |
| Frontend | Streamlit (MVP) | Fastest path to a usable UI for forms + result cards; can be swapped for React later without touching the core |
| Config/secrets | `pydantic-settings` + `.env` | Centralized, typed config; keeps API keys out of source |
| Testing | `pytest` | Unit tests for filtering logic and prompt construction; mocked LLM responses |
| Packaging | `Docker` + `docker-compose` | Reproducible local/dev environment; separates API and UI containers |

> These are recommendations for a clean MVP, not hard requirements — the core/data layers are framework-agnostic and can be re-hosted behind a different frontend or LLM provider later (see [Section 9](#9-extensibility--future-enhancements)).

## 4. Component Design

### 4.1 Data Ingestion Layer (`data/`)

- **`loader.py`** — Downloads the dataset from Hugging Face (`ManikaSaini/zomato-restaurant-recommendation`) once, caches it locally as a Parquet file (`data/cache/zomato.parquet`). Subsequent runs load from cache unless a `--refresh` flag/env var forces a re-pull.
- **`preprocessor.py`** — Cleans and normalizes raw fields into a consistent schema:
  - Trim/normalize `location` and `city` strings (case-insensitive matching).
  - Split multi-value `cuisine` strings (e.g., `"North Indian, Chinese"`) into a list for containment checks.
  - Parse `cost` into a numeric value and derive a `budget_tier` (`low` / `medium` / `high`) via quantile or fixed thresholds.
  - Coerce `rating` to float; drop or flag rows with missing/invalid ratings.
  - Deduplicate restaurants (same name + location appearing multiple times in raw data).
- **`schema.py`** — Defines the canonical `Restaurant` record (Pydantic model or dataclass) used everywhere downstream: `name, location, cuisines: list[str], cost, budget_tier, rating, extra_attributes`.

### 4.2 API Layer (`api/`)

- **`main.py`** — FastAPI app instance, CORS setup, startup hook that triggers dataset load into an in-memory singleton (avoids re-loading per request).
- **`routes/recommendations.py`** — `POST /recommendations`:
  - Request body: `UserPreferences` (location, budget, cuisine, min_rating, extra_preferences: str).
  - Response body: `RecommendationResponse` (list of ranked restaurants + explanations + optional summary).
- **`models.py`** — Pydantic request/response schemas, decoupled from the internal `Restaurant` record.

### 4.3 Filtering Engine (`core/filter.py`)

- Applies hard filters against the cached DataFrame:
  - `location` (case-insensitive match, optionally fuzzy)
  - `budget_tier` (maps `low/medium/high` to cost ranges)
  - `cuisine` (containment check against the cuisine list)
  - `rating >= min_rating`
- Sorts remaining candidates by `rating desc, cost asc` and truncates to **top 15–20 candidates** before they ever reach the LLM — this bounds prompt size/cost and keeps latency predictable.
- If zero results after filtering, progressively relaxes constraints (drop cuisine, then budget, then rating) and flags the response as "relaxed filters used" so the UI/LLM can be transparent about it.

### 4.4 Prompt Builder (`core/prompt_builder.py`)

- Builds a system prompt establishing the assistant's role ("You are a restaurant recommendation expert...") and output contract.
- Injects the filtered candidate list as compact structured data (JSON) rather than prose, to keep token usage low and make the input unambiguous to the model.
- Includes the user's raw free-text preferences (e.g., "family-friendly") as context the LLM should reason over, since these aren't captured by the hard filters.
- Also instructs the model to treat the free-text preferences strictly as data to reason about, never as instructions to follow — mitigates prompt injection via that field (see edge-cases.md).
- Requests a **structured JSON output** via Groq's OpenAI-compatible tool/function-calling (not free-form text) so the response is deterministic to parse — schema: `{ recommendations: [{ name, cuisine, rating, cost, explanation }], summary }`.

### 4.5 LLM Client (`core/llm_client.py`)

- Thin wrapper around the `groq` SDK: builds the request, attaches the tool schema (with `tool_choice` forcing that specific tool), handles timeouts/retries (exponential backoff, max 3 attempts) for retryable errors (rate limit, timeout, connection, 5xx); non-retryable errors (auth, bad request) fail fast without retrying.
- Model selection is config-driven (`openai/gpt-oss-120b` default; `qwen/qwen3.6-27b` is a supported alternative via the same env var).
- Validates the response is grounded in the candidate list (every recommended name must match a candidate exactly) before returning it — a hallucinated restaurant is treated as an LLM failure, not returned to the user.
- Enforces the model's published rate limits client-side via `core/rate_limiter.py` (`SlidingWindowRateLimiter`, config-driven: `LLM_REQUESTS_PER_MINUTE`/`_PER_DAY`, `LLM_TOKENS_PER_MINUTE`/`_PER_DAY`) before every attempt, so the app degrades to the fallback ranker predictably instead of retry-looping against real 429s. Token cost per call is estimated pre-flight (calibrated against real usage) and corrected with the API's actual `usage.total_tokens` afterward. On `openai/gpt-oss-120b`'s free tier, the 8K-tokens-per-minute limit is the binding constraint, not the 30-requests-per-minute limit — a single max-size (20-candidate) call runs ~2,400 tokens, so only ~3-5 LLM-backed recommendations are sustainable per minute before falling back.
- On repeated failure, malformed structured output, or a groundedness violation, raises a typed exception that the API layer catches to invoke the fallback path.

### 4.6 Fallback Ranker (`core/fallback.py`)

- Pure-pandas ranking (e.g., weighted score of rating and cost) used when the LLM is unavailable or errors out repeatedly.
- Explanations in this path are template-generated (e.g., "Highly rated {cuisine} option within your budget in {location}") rather than LLM-authored, so the API never returns an empty result to the user.

### 4.7 Frontend (`frontend/`)

- Streamlit app (`app.py`) with a form for location, budget, cuisine, min rating, and a free-text field for extra preferences.
- Calls the FastAPI backend over HTTP; renders results as cards (name, cuisine tags, rating badge, cost, explanation text).
- Shows a non-blocking notice when the backend used the fallback ranker or relaxed filters.

### 4.8 Config (`config.py`)

- `pydantic-settings` `Settings` class reading from `.env`: `GROQ_API_KEY`, `LLM_MODEL`, `DATASET_NAME`, `CACHE_DIR`, `MAX_CANDIDATES_TO_LLM`, `LOG_LEVEL`, `LLM_REQUESTS_PER_MINUTE`, `LLM_REQUESTS_PER_DAY`, `LLM_TOKENS_PER_MINUTE`, `LLM_TOKENS_PER_DAY`, `LLM_RATE_LIMIT_MAX_WAIT_SECONDS`.

## 5. Data Flow (Sequence)

```mermaid
sequenceDiagram
    participant U as User (UI)
    participant A as FastAPI
    participant F as Filtering Engine
    participant P as Prompt Builder
    participant L as LLM (Groq)
    participant C as Cached Dataset

    U->>A: POST /recommendations (preferences)
    A->>F: filter(preferences)
    F->>C: query DataFrame
    C-->>F: matching rows
    F-->>A: top-N candidates (or relaxed set)
    A->>P: build_prompt(candidates, preferences)
    P->>L: request (tool-use, JSON schema)
    alt success
        L-->>A: structured recommendations + explanations
    else failure/timeout
        A->>A: fallback_rank(candidates)
    end
    A-->>U: ranked results (JSON)
    U->>U: render restaurant cards
```

## 6. Proposed Folder Structure

```
test-ai-project/
├── docs/
│   ├── problemStatement.md
│   └── architecture.md
├── data/
│   ├── loader.py
│   ├── preprocessor.py
│   ├── schema.py
│   └── cache/                  # gitignored, holds cached parquet
├── core/
│   ├── filter.py
│   ├── prompt_builder.py
│   ├── llm_client.py
│   └── fallback.py
├── api/
│   ├── main.py
│   ├── models.py
│   └── routes/
│       └── recommendations.py
├── frontend/
│   └── app.py
├── tests/
│   ├── test_filter.py
│   ├── test_prompt_builder.py
│   └── test_api.py
├── config.py
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 7. Error Handling & Edge Cases

| Scenario | Handling |
|---|---|
| No restaurants match all filters | Progressively relax filters (cuisine → budget → rating); surface which constraints were relaxed |
| LLM API error/timeout | Retry with backoff; after max attempts, use fallback ranker so the user always gets a response |
| LLM returns malformed/non-JSON output | Validate against the tool-use schema; on failure, treat as an LLM error and fall back |
| Missing/dirty dataset fields (null rating, empty cuisine) | Dropped or defaulted during preprocessing; never passed downstream with nulls |
| Dataset unavailable at startup (HF down, first run) | Load from local cache if present; fail startup clearly if no cache and no network |
| Very large candidate set after filtering | Hard cap at top 15–20 by rating/cost before prompt construction |

## 8. Non-Functional Considerations

- **Cost control**: pre-filtering in pandas keeps the LLM prompt small and bounded regardless of dataset size; model choice is configurable to trade quality for cost.
- **Latency**: dataset loaded once into memory at API startup (not per-request); LLM call is the dominant latency cost — consider async/streaming in a later iteration.
- **Testability**: filtering and prompt-building are pure functions over data, testable without any LLM calls; LLM client is mocked in tests via a fixed fake response.
- **Observability**: log filter parameters, candidate count, LLM latency, and whether fallback was used, to make quality issues (e.g., always falling back) visible.

## 9. Extensibility & Future Enhancements

- **Semantic matching**: add embeddings-based search (e.g., for fuzzy cuisine/location matching or free-text preference matching) if keyword/tag filtering proves too rigid.
- **Conversational refinement**: support multi-turn follow-ups ("show me cheaper options") by keeping prior filtered candidates and preferences in session state.
- **Persistence**: add SQLite/Postgres if user history, saved preferences, or feedback loops (thumbs up/down on recommendations) are required.
- **Alternate frontend**: the API is framework-agnostic — Streamlit can be replaced with a React/Next.js frontend without changing `core/` or `data/`.
- **Alternate LLM provider**: `llm_client.py` isolates all Groq-specific code, so swapping providers (or switching between `openai/gpt-oss-120b` and `qwen/qwen3.6-27b`, or another Groq-hosted model) touches one module.
