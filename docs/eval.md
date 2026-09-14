# Evaluation Plan: AI-Powered Restaurant Recommendation System

Defines how to evaluate the system built per [implementation-plan.md](./implementation-plan.md) — beyond unit/integration tests (which check code correctness), this covers whether the **recommendations themselves are good**: relevant, grounded in the real candidate data, well-explained, and reliable under failure. Also see [edge-cases.md](./edge-cases.md) for the specific inputs this eval should exercise.

## 1. Why a Separate Eval Layer

`pytest` (Phases 1–4 of the implementation plan) verifies the code does what it's supposed to — filtering logic, API contracts, mocked LLM responses. It cannot tell you whether the *actual* LLM output, against the *actual* dataset, is a recommendation a real user would find useful. That requires a distinct evaluation pass with its own dataset, metrics, and (partly) human judgment.

| | Unit/integration tests | Evaluation (this doc) |
|---|---|---|
| Checks | Code behaves correctly given fixed/mocked inputs | Real LLM output quality against real data |
| Runs | Every commit / CI | On prompt changes, model changes, and periodically |
| Pass/fail | Deterministic | Metrics + thresholds, some requiring human/LLM-judge scoring |

## 2. What Gets Evaluated

1. **Groundedness** — every recommended restaurant must actually be in the filtered candidate list; no hallucinated names, cuisines, ratings, or costs.
2. **Relevance** — recommendations should genuinely fit the stated preferences (location, budget, cuisine, min rating) and reasonably address free-text preferences (e.g., "family-friendly").
3. **Explanation quality** — each explanation should be specific to that restaurant (not generic boilerplate reused across results) and consistent with the data shown (doesn't claim a cost tier or attribute the data doesn't support).
4. **Ranking quality** — the order should make sense given the data (e.g., not burying the highest-rated in-budget option under a lower-rated one without justification).
5. **Schema/format reliability** — structured output parses correctly, matches the response contract, on the first attempt (not just eventually after retries).
6. **Robustness** — behavior across the edge cases in `edge-cases.md` (tiny candidate sets, relaxed filters, near-duplicate restaurants, adversarial free text).
7. **System-level reliability** — fallback trigger rate, latency, and cost stay within acceptable bounds under realistic query volume.

## 3. Golden Query Set

A fixed set of representative preference inputs, run consistently across evaluation cycles so results are comparable over time. Store as `eval/golden_queries.jsonl` (one JSON object per line: preferences + optional notes on what to check).

**Coverage required**:

- At least 2–3 major cities represented in the dataset, plus one city with sparse data (few restaurants).
- All three budget tiers, and a combination that yields zero results at the intersection (forces relaxation).
- Common cuisines and at least one cuisine not present in the dataset at all.
- Boundary `min_rating` values (exact match to an existing rating; above the dataset max).
- A handful of free-text preferences: benign ("family-friendly", "quick service"), vague ("something nice"), and adversarial (attempted prompt injection, per edge-cases.md).
- At least one query engineered to produce a very small candidate set (1–2 restaurants) and one to hit the 15–20 cap exactly.

Target size: ~30–50 queries — enough for coverage, small enough to review by hand each cycle.

## 4. Metrics & Scoring

| Metric | Definition | How measured | Target |
|---|---|---|---|
| Schema validity rate | % of LLM responses parsing into the expected structured schema on first attempt | Automated, from LLM client logs | ≥ 98% |
| Hallucination rate | % of recommended restaurants not present in the candidate list, or with attributes (rating/cost/cuisine) that don't match the source data | Automated cross-check: response vs. candidate list | 0% (hard requirement — any occurrence is a bug, not a quality nit) |
| Relevance score | 1–5 rubric: does the recommendation set fit the stated preferences? | LLM-as-judge and/or human spot-check | Avg ≥ 4.0 |
| Explanation quality score | 1–5 rubric: specific, accurate, non-repetitive across results in the same response | LLM-as-judge and/or human spot-check | Avg ≥ 4.0 |
| Fallback trigger rate | % of golden queries where the non-LLM fallback ranker was used | Automated, from API response flag | < 5% under normal operation (excluding intentionally-forced-failure test runs) |
| Relaxation rate | % of golden queries where filters had to be relaxed | Automated, from API response flag | Informational — expected to be nonzero for the intentionally sparse queries; investigate if it's high across "realistic" queries |
| p50 / p95 latency | End-to-end response time for `/recommendations` | Automated timing harness | p50 < 3s, p95 < 8s (tune once real model latency is known) |
| Cost per request | Tokens in/out × model pricing | Automated, from API usage metadata | Track trend; flag if candidate cap is silently exceeded (see edge-cases.md "cost creep") |

### Rubric-based scores (Relevance, Explanation quality)

Score each golden query's response 1–5:

- **5** — Every recommendation fits all stated hard constraints; explanations are specific, accurate, and each one adds distinct information.
- **3** — Recommendations mostly fit; explanations are present but generic or slightly repetitive.
- **1** — Recommendations ignore stated constraints, or explanations are inaccurate/boilerplate/absent.

Use an **LLM-as-judge** pass (a separate Claude call given the preferences, candidates, and response, asked to score against this rubric) for scale, plus a **human spot-check** of a random 10–15% sample each cycle to catch judge drift or blind spots the judge itself might share with the model being evaluated.

## 5. Evaluation Methodology

1. **Fixture the dataset**: run eval against a pinned snapshot of the preprocessed dataset (not a live re-download) so results are comparable across runs — changes in the underlying HF dataset shouldn't silently shift eval outcomes.
2. **Run the golden set** through the real pipeline (filter → prompt → LLM, fallback disabled/forced-off unless specifically testing the fallback path) and capture: preferences, candidates, raw LLM response, parsed response, latency, token usage.
3. **Automated checks first**: schema validity, hallucination check (recommended items ⊆ candidate list, attributes match), cap enforcement, relaxation/fallback flags — these are pass/fail, no judgment needed.
4. **LLM-as-judge pass**: score relevance and explanation quality per the rubric above.
5. **Human spot-check**: sample and manually review, focusing especially on adversarial free-text queries (did the model resist injection?) and edge queries (sparse candidates, relaxed filters).
6. **Aggregate report**: per-metric summary + full per-query detail for anything scoring below threshold, so failures are diagnosable, not just visible as a number.

## 6. Tooling

- `eval/golden_queries.jsonl` — the fixed query set (§3).
- `eval/run_eval.py` — drives the golden set through the pipeline, runs automated checks, invokes the LLM-judge pass, writes a report (`eval/results/<timestamp>.json` + a human-readable summary).
- `eval/judge_prompt.md` — the rubric prompt used for the LLM-as-judge pass, versioned so scoring criteria changes are tracked over time.
- Reuse `core/filter.py`, `core/prompt_builder.py`, `core/llm_client.py` directly (no duplicate pipeline logic) — the eval harness is a caller of the real core modules, not a reimplementation.

## 7. When to Run

| Trigger | What to run |
|---|---|
| Every prompt change (`prompt_builder.py`) | Full golden set + judge pass |
| Every model change (e.g., switching `LLM_MODEL`) | Full golden set + judge pass, compare against prior model's results |
| End of implementation-plan Phase 3 (LLM Integration) | Full golden set — this is the concrete "manual smoke test" called for in that phase, formalized |
| End of implementation-plan Phase 6 (Hardening) | Full golden set + latency/cost metrics, as part of the non-functional sign-off |
| Periodically in production (if deployed) | Sample of live queries (anonymized) added to a rotating eval set to catch drift the fixed golden set doesn't cover |

## 8. Regression Policy

- Automated checks (hallucination rate, schema validity, cap enforcement) are **hard gates** — any regression blocks the change.
- Rubric scores (relevance, explanation quality) are **soft gates** — a drop of more than ~0.5 points average, or any individual query dropping from ≥4 to ≤2, should be investigated and explained (prompt tradeoff, model change, etc.) before merging, even if not auto-blocking.
- Record eval results alongside the change that produced them (e.g., in the PR description or `eval/results/`) so quality trends over time are visible, not just the latest snapshot.

## 9. Known Limitations of This Eval Approach

- LLM-as-judge shares failure modes with the model being judged (may share blind spots or biases) — human spot-checks exist specifically to catch this, not as a redundant formality.
- The golden set is necessarily small relative to the full space of possible preference combinations; it catches known edge cases (per edge-cases.md) but won't surface every unknown one — production sampling (§7) is the long-term mitigation.
- Explanation "quality" is inherently subjective; the rubric reduces but doesn't eliminate scoring variance between runs/judges.
