import json
import logging
import time

from groq import (
    APIConnectionError,
    APITimeoutError,
    Groq,
    InternalServerError,
    RateLimitError,
)
from pydantic import ValidationError

from config import get_settings
from core.models import RecommendationResult, UserPreferences
from core.prompt_builder import RECOMMENDATION_TOOL, TOOL_NAME, build_messages
from core.rate_limiter import RateLimitBudgetExceeded, SlidingWindowRateLimiter
from data.schema import Restaurant

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

# Rough token estimator for the pre-flight rate-limit check, calibrated
# against real Groq responses: chars/4 underestimated actual prompt_tokens
# by 5-20% (tool schema + JSON overhead isn't 1:1 with plain-English chars),
# and completion_tokens (including this model's internal reasoning tokens)
# ran 660-770 regardless of candidate count in testing. Overestimating here
# is safe -- it just throttles slightly earlier -- underestimating risks a
# real 429 from the provider.
CHARS_PER_TOKEN_ESTIMATE = 4
PROMPT_ESTIMATE_SAFETY_MARGIN = 1.3
RESERVED_COMPLETION_TOKENS = 1000


logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails, or returns output that can't be trusted."""


def _client() -> Groq:
    return Groq(api_key=get_settings().groq_api_key)


def _estimate_tokens(messages: list[dict]) -> int:
    tool_chars = len(json.dumps(RECOMMENDATION_TOOL))
    message_chars = sum(len(m["content"]) for m in messages)
    estimated_prompt_tokens = (
        (message_chars + tool_chars) / CHARS_PER_TOKEN_ESTIMATE
    ) * PROMPT_ESTIMATE_SAFETY_MARGIN
    return int(estimated_prompt_tokens) + RESERVED_COMPLETION_TOKENS


_rate_limiter: SlidingWindowRateLimiter | None = None


def _get_rate_limiter() -> SlidingWindowRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = SlidingWindowRateLimiter(
            requests_per_minute=settings.llm_requests_per_minute,
            requests_per_day=settings.llm_requests_per_day,
            tokens_per_minute=settings.llm_tokens_per_minute,
            tokens_per_day=settings.llm_tokens_per_day,
            max_wait_seconds=settings.llm_rate_limit_max_wait_seconds,
        )
    return _rate_limiter


def get_recommendations(
    candidates: list[Restaurant], preferences: UserPreferences
) -> RecommendationResult:
    """Call the LLM to rank/explain candidates, retrying on transient errors.

    Raises LLMError (never returns a partial/untrusted result) if the call
    fails after retries, returns malformed output, recommends a restaurant
    not present in `candidates`, or would exceed the configured client-side
    rate-limit budget -- callers should catch this and fall through to
    core.fallback.fallback_rank.
    """
    settings = get_settings()

    # Defense-in-depth: core.filter already caps candidates at
    # max_candidates_to_llm before this is ever called, but truncate again
    # here so a future bug in an upstream caller can't silently blow the
    # per-call token/cost budget.
    if len(candidates) > settings.max_candidates_to_llm:
        logger.warning(
            "Received %d candidates, more than max_candidates_to_llm=%d -- truncating",
            len(candidates),
            settings.max_candidates_to_llm,
        )
        candidates = candidates[: settings.max_candidates_to_llm]

    messages = build_messages(candidates, preferences)
    client = _client()
    rate_limiter = _get_rate_limiter()
    estimated_tokens = _estimate_tokens(messages)

    logger.info(
        "Groq call starting: model=%s candidates=%d estimated_tokens=%d",
        settings.llm_model,
        len(candidates),
        estimated_tokens,
    )
    start = time.monotonic()

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            rate_limiter.acquire(estimated_tokens)
        except RateLimitBudgetExceeded as exc:
            logger.warning("Local rate-limit budget exceeded, skipping Groq call: %s", exc)
            raise LLMError(f"Local rate-limit budget exceeded: {exc}") from exc

        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=[RECOMMENDATION_TOOL],
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
                temperature=0,
            )
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            logger.warning(
                "Groq call attempt %d/%d failed (retryable): %s", attempt, MAX_ATTEMPTS, exc
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            raise LLMError(
                f"Groq API call failed after {MAX_ATTEMPTS} attempts: {exc}"
            ) from exc
        except Exception as exc:
            logger.warning("Groq call failed (non-retryable): %s", exc)
            raise LLMError(f"Groq API call failed: {exc}") from exc
        else:
            elapsed = time.monotonic() - start
            tokens_used = response.usage.total_tokens if response.usage is not None else -1
            if response.usage is not None:
                rate_limiter.record_actual_tokens(estimated_tokens, tokens_used)
            try:
                result = _parse_response(response, candidates)
            except LLMError as exc:
                logger.warning(
                    "Groq call returned untrustworthy output after %.2fs (tokens=%d): %s",
                    elapsed,
                    tokens_used,
                    exc,
                )
                raise
            logger.info(
                "Groq call succeeded in %.2fs (attempt %d/%d, tokens=%d, recommendations=%d)",
                elapsed,
                attempt,
                MAX_ATTEMPTS,
                tokens_used,
                len(result.recommendations),
            )
            return result

    raise LLMError(f"Groq API call failed: {last_error}") from last_error


def _parse_response(response, candidates: list[Restaurant]) -> RecommendationResult:
    choice = response.choices[0]
    tool_calls = choice.message.tool_calls
    if not tool_calls:
        raise LLMError("Model did not return a tool call")

    try:
        arguments = json.loads(tool_calls[0].function.arguments)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model tool call arguments were not valid JSON: {exc}") from exc

    try:
        result = RecommendationResult(
            recommendations=arguments.get("recommendations", []),
            summary=arguments.get("summary"),
            source="llm",
        )
    except ValidationError as exc:
        raise LLMError(f"Model output did not match the expected schema: {exc}") from exc

    _validate_grounded(result, candidates)
    return result


def _validate_grounded(result: RecommendationResult, candidates: list[Restaurant]) -> None:
    if not result.recommendations:
        raise LLMError("Model returned zero recommendations")

    candidate_names = {c.name for c in candidates}
    hallucinated = [r.name for r in result.recommendations if r.name not in candidate_names]
    if hallucinated:
        raise LLMError(f"Model recommended restaurants not in the candidate list: {hallucinated}")
