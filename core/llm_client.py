import json
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
from data.schema import Restaurant

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


class LLMError(Exception):
    """Raised when the LLM call fails, or returns output that can't be trusted."""


def _client() -> Groq:
    return Groq(api_key=get_settings().groq_api_key)


def get_recommendations(
    candidates: list[Restaurant], preferences: UserPreferences
) -> RecommendationResult:
    """Call the LLM to rank/explain candidates, retrying on transient errors.

    Raises LLMError (never returns a partial/untrusted result) if the call
    fails after retries, returns malformed output, or recommends a
    restaurant not present in `candidates` -- callers should catch this and
    fall through to core.fallback.fallback_rank.
    """
    settings = get_settings()
    messages = build_messages(candidates, preferences)
    client = _client()

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
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
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            raise LLMError(
                f"Groq API call failed after {MAX_ATTEMPTS} attempts: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMError(f"Groq API call failed: {exc}") from exc
        else:
            return _parse_response(response, candidates)

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
