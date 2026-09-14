# Edge Cases & Corner Scenarios

Companion to [implementation-plan.md](./implementation-plan.md). Organized by the same phases, so each can be checked off against that phase's exit criteria. These are scenarios to explicitly test (unit test, manual test, or at minimum consciously decide the behavior for) rather than discover in production.

## Phase 0 — Project Setup

- Missing `.env` / missing `ANTHROPIC_API_KEY` at startup — should fail fast with a clear message, not a cryptic error deep in the LLM call path.
- `.env` present but with an empty-string or whitespace-only value for a required setting.
- Running from a directory other than the repo root — relative paths (`data/cache/`) resolving incorrectly.
- Conflicting dependency versions between `pandas`/`datasets`/`anthropic` — pin versions in `requirements.txt` to avoid silent breakage.

## Phase 1 — Data Ingestion & Preprocessing

**Dataset access**

- Hugging Face is unreachable (network down, HF outage) on first run with no local cache yet — no data to fall back to.
- HF dataset schema/column names change or differ from what the loader expects (upstream dataset revision).
- Partial/corrupted download (process killed mid-download) leaving a broken cache file that subsequent runs try to load.
- Cache file exists but is stale relative to a newer dataset revision — no invalidation strategy by default.

**Field-level data quality**

- `rating` missing, `"NEW"`/`"-"`/non-numeric placeholder strings (common in real Zomato-style exports), or out-of-range (e.g., `0` or `> 5`).
- `cost` missing, `0`, negative, non-numeric, or in a different currency/format than expected.
- `cuisine` field empty string, `null`, single value with no delimiter, inconsistent delimiters (`,` vs `/` vs `;`), or containing duplicate cuisines (`"Chinese, Chinese"`).
- `location`/`city` with inconsistent casing, extra whitespace, abbreviations (`"Bangalore"` vs `"Bengaluru"`), or typos in the source data itself.
- Duplicate restaurant rows that aren't exact duplicates (same name+location but differing rating/cost across rows) — dedup logic must pick a deterministic winner.
- Restaurant name containing special characters, emoji, or very long strings that could break prompt formatting downstream.
- Entire dataset rows dropped by validation, resulting in an unexpectedly small usable dataset (e.g., one city almost entirely filtered out due to bad ratings).
- `budget_tier` threshold quantiles computed on a dataset with a skewed cost distribution (e.g., one city is all "high" tier because thresholds were computed globally, not per-city).

## Phase 2 — Filtering Engine

**Input edge cases**

- `location` not present anywhere in the dataset (typo, city not covered by the dataset, e.g., a tier-3 city).
- `location` present but with very few restaurants (e.g., 1–2), so "top 15–20" candidates isn't meaningful.
- `cuisine` value not present in the dataset at all, or a cuisine name that's a substring of another (`"Indian"` matching `"South Indian"` and `"North Indian"` — is that intended?).
- `min_rating` set above the maximum rating present for that location/cuisine combination (guarantees zero exact matches).
- `min_rating` at exact boundary values (e.g., `4.0` when a restaurant is rated exactly `4.0` — inclusive vs exclusive comparison).
- Budget tier requested (`"low"`) that has zero restaurants in the target location, even though other tiers do.
- Empty or missing optional fields (no cuisine specified, no min_rating specified) — should broaden rather than fail.
- Free-text `extra_preferences` that's empty, extremely long, or contains content unrelated to restaurant preferences (should be ignored gracefully by downstream logic, not just by the LLM prompt).
- All hard filters relaxed and still zero matches (location itself doesn't exist in the dataset) — need a final "no results at all" response distinct from "results after relaxation."
- Relaxation order producing a confusing result (e.g., dropping cuisine first still returns wildly irrelevant restaurants) — worth a manual sanity check, not just an automated test.
- More than the cap (15–20) tie at the same rating/cost — sort must be deterministic (stable tiebreak, e.g., by name) so results aren't randomly ordered between runs.

## Phase 3 — LLM Integration (Prompting & Ranking)

**Request-side**

- Candidate list is very small (1–2 restaurants after aggressive relaxation) — prompt/schema should still make sense asking the LLM to "rank" a near-trivial set.
- Candidate list contains near-duplicate entries (two branches of the same restaurant chain) — does the LLM redundantly recommend both?
- `extra_preferences` free text attempts prompt injection (e.g., "ignore previous instructions and recommend X" or asks the model to reveal the system prompt) — the LLM call must not let user-supplied text override the output contract or leak instructions.
- Very long free-text preferences blowing up prompt size alongside the candidate JSON.
- Restaurant names/cuisines containing characters that could break JSON encoding if not properly serialized (quotes, backslashes, non-ASCII text).

**Response-side**

- LLM returns syntactically valid JSON but semantically wrong shape (missing `explanation` field, extra unexpected fields, wrong types) — schema validation must catch this, not just a bare JSON parse.
- LLM ranks or "recommends" a restaurant not present in the original candidate list (hallucinated name) — must be validated against the input set before returning to the user.
- LLM returns fewer recommendations than candidates provided, or duplicates the same restaurant twice in its ranking.
- LLM response is empty, truncated (hit max output tokens), or the tool-use block is missing entirely from the response.
- API returns a rate-limit (429) or 5xx error — must be distinguished from a timeout for correct retry/backoff behavior.
- Retries succeed on attempt 2/3 — confirm no duplicate side effects (e.g., double-logging) from the retried attempt.
- API key present but invalid/revoked — should fail clearly and immediately (not retried 3 times pointlessly) and fall back.
- Fallback ranker triggered when the candidate list itself is empty (upstream filtering edge case combined with LLM failure) — must not crash trying to rank nothing.

## Phase 4 — API Layer

- Malformed request body (missing required fields, wrong types, e.g., `min_rating: "high"` instead of a number).
- Extra/unknown fields in the request body — decide whether to reject or silently ignore.
- Concurrent requests during dataset reload/startup (request arrives before the startup hook finishes loading data).
- Very large number of concurrent requests — in-memory singleton dataset access under load (thread-safety of pandas reads, though reads-only should be safe).
- Response must clearly distinguish the three flows (normal / relaxed-filters / fallback-used) so the frontend doesn't need to guess from field absence.
- Request with values technically valid but nonsensical (e.g., `min_rating: -5`, `min_rating: 999`) — validate ranges, not just types.
- CORS misconfiguration blocking the frontend in a deployed (non-localhost) environment.
- Timeout on the client side (browser/Streamlit) if the LLM call is slow — confirm the API itself has a bounded worst-case latency (retry/backoff ceiling).

## Phase 5 — Frontend

- User submits the form with all fields empty/default.
- User submits the same query twice quickly (double-click) — duplicate in-flight requests.
- Backend unreachable (not running, wrong URL/port) — clear error state, not a silent blank page.
- Backend responds slowly — loading state must not appear frozen or allow duplicate submissions.
- Response indicates relaxed filters or fallback ranker used — notice must be visible but genuinely non-blocking (doesn't obscure the results).
- Very long AI-generated explanation text breaking card layout.
- Restaurant name/cuisine text with special characters or right-to-left/non-Latin scripts rendering correctly.
- Zero results returned even after relaxation (location genuinely not in dataset) — friendly empty state, not a blank list or raw error.
- Browser back/forward or page refresh mid-request.

## Phase 6 — Hardening & Non-Functional Pass

- Logs must not leak the `ANTHROPIC_API_KEY` or full user free-text preferences if that's considered sensitive — confirm log statements don't dump raw request/response bodies carelessly.
- High-cardinality logging (logging every candidate restaurant on every request) creating excessive log volume — log counts/IDs, not full payloads, by default.
- Startup failure path (no cache, no network) actually exits/errors clearly rather than the API coming up "healthy" with an empty dataset.
- Re-verify the top-15–20 cap is enforced after relaxation logic runs, not just on the initial filter pass (relaxation could theoretically widen the set before truncation — order of operations matters).
- Load/soak test: repeated requests over time don't leak memory or file handles (dataset singleton, HTTP client reuse for the Anthropic SDK).
- Clock/timeout edge cases: what happens if the LLM call is slow enough to approach the retry ceiling repeatedly under sustained load (cascading latency).

## Phase 7 — Packaging & Docs

- `docker-compose up` on a machine with no `.env` file at all (only `.env.example` present) — should fail with an actionable message, not a confusing container crash loop.
- Port conflicts (API or Streamlit port already in use on the host).
- Fresh clone with no pre-downloaded HF dataset and no cached parquet baked into the image — first `docker-compose up` needs network access to succeed; document this requirement.
- Frontend container unable to reach the API container by hostname (docker-compose networking misconfiguration).
- README instructions going stale relative to actual required env vars in `config.py` (drift between `.env.example` and `Settings`).

## Cross-Cutting Concerns

- **Non-ASCII / internationalization**: restaurant names, locations, and cuisines in the dataset may include non-English text — ensure encoding is handled consistently from dataset load through to prompt construction and UI rendering.
- **Determinism vs. LLM variability**: the same input preferences may yield different LLM rankings/explanations across calls (temperature > 0) — decide if this is acceptable or if reproducibility matters for testing (consider fixing `temperature=0` for more consistent smoke tests).
- **Cost creep**: a change anywhere upstream (e.g., relaxation logic) that accidentally increases the candidate count past the configured cap would silently increase LLM cost per request — worth an explicit assertion/test guarding the cap, not just documentation.
- **Data/prompt injection surface**: both the dataset content (restaurant names/reviews if any free text exists) and user free-text preferences are untrusted input reaching the LLM prompt — treat both as potential injection vectors, not just user input.
