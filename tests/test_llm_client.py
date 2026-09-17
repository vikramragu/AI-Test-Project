import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import APITimeoutError, AuthenticationError, RateLimitError

from core.llm_client import LLMError, get_recommendations
from core.models import UserPreferences
from data.schema import Restaurant

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def make_restaurant(**overrides) -> Restaurant:
    defaults = dict(
        name="Spice Route",
        location="Koramangala",
        cuisines=["North Indian"],
        cost=800.0,
        budget_tier="high",
        rating=4.5,
        extra_attributes={},
    )
    defaults.update(overrides)
    return Restaurant(**defaults)


def make_response(arguments: dict | str, tool_calls: bool = True):
    args_str = arguments if isinstance(arguments, str) else json.dumps(arguments)
    tool_call = SimpleNamespace(function=SimpleNamespace(name="provide_recommendations", arguments=args_str))
    message = SimpleNamespace(tool_calls=[tool_call] if tool_calls else [])
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_tokens=1234)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Each test gets a fresh rate limiter built from real settings, so
    accumulated usage from other tests can't cause spurious throttling."""
    import core.llm_client as llm_client_module

    llm_client_module._rate_limiter = None
    yield
    llm_client_module._rate_limiter = None


VALID_ARGS = {
    "recommendations": [
        {
            "name": "Spice Route",
            "cuisine": "North Indian",
            "rating": 4.5,
            "cost": 800.0,
            "explanation": "Highly rated and matches your cuisine preference.",
        }
    ],
    "summary": "A great pick for North Indian food.",
}


@pytest.fixture
def preferences() -> UserPreferences:
    return UserPreferences(location="Koramangala", cuisine="North Indian")


@patch("core.llm_client._client")
def test_success_path_parses_recommendations(mock_client_factory, preferences):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_response(VALID_ARGS)
    mock_client_factory.return_value = mock_client

    result = get_recommendations([make_restaurant()], preferences)

    assert result.source == "llm"
    assert len(result.recommendations) == 1
    assert result.recommendations[0].name == "Spice Route"
    assert result.summary == "A great pick for North Indian food."
    assert mock_client.chat.completions.create.call_count == 1


@patch("core.llm_client._client")
def test_no_tool_call_raises_llm_error(mock_client_factory, preferences):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_response({}, tool_calls=False)
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError, match="did not return a tool call"):
        get_recommendations([make_restaurant()], preferences)


@patch("core.llm_client._client")
def test_malformed_json_raises_llm_error(mock_client_factory, preferences):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_response("{not valid json")
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError, match="not valid JSON"):
        get_recommendations([make_restaurant()], preferences)


@patch("core.llm_client._client")
def test_hallucinated_restaurant_raises_llm_error(mock_client_factory, preferences):
    mock_client = MagicMock()
    bad_args = {
        "recommendations": [
            {
                "name": "Restaurant That Does Not Exist",
                "cuisine": "North Indian",
                "rating": 5.0,
                "cost": 100.0,
                "explanation": "Made up.",
            }
        ],
        "summary": "N/A",
    }
    mock_client.chat.completions.create.return_value = make_response(bad_args)
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError, match="not in the candidate list"):
        get_recommendations([make_restaurant()], preferences)


@patch("core.llm_client._client")
def test_empty_recommendations_raises_llm_error(mock_client_factory, preferences):
    mock_client = MagicMock()
    empty_args = {"recommendations": [], "summary": "Nothing fits."}
    mock_client.chat.completions.create.return_value = make_response(empty_args)
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError, match="zero recommendations"):
        get_recommendations([make_restaurant()], preferences)


@patch("time.sleep", return_value=None)
@patch("core.llm_client._client")
def test_retryable_error_retries_then_succeeds(mock_client_factory, mock_sleep, preferences):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        APITimeoutError(request=REQUEST),
        make_response(VALID_ARGS),
    ]
    mock_client_factory.return_value = mock_client

    result = get_recommendations([make_restaurant()], preferences)

    assert result.source == "llm"
    assert mock_client.chat.completions.create.call_count == 2


@patch("time.sleep", return_value=None)
@patch("core.llm_client._client")
def test_retryable_error_exhausts_retries_and_raises(mock_client_factory, mock_sleep, preferences):
    mock_client = MagicMock()
    response = httpx.Response(status_code=429, request=REQUEST)
    mock_client.chat.completions.create.side_effect = RateLimitError(
        "rate limited", response=response, body=None
    )
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError, match="failed after 3 attempts"):
        get_recommendations([make_restaurant()], preferences)

    assert mock_client.chat.completions.create.call_count == 3


@patch("core.llm_client._client")
def test_non_retryable_error_fails_immediately(mock_client_factory, preferences):
    mock_client = MagicMock()
    response = httpx.Response(status_code=401, request=REQUEST)
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        "bad key", response=response, body=None
    )
    mock_client_factory.return_value = mock_client

    with pytest.raises(LLMError):
        get_recommendations([make_restaurant()], preferences)

    assert mock_client.chat.completions.create.call_count == 1


@patch("core.llm_client._get_rate_limiter")
@patch("core.llm_client._client")
def test_local_rate_limit_budget_exceeded_never_calls_api(
    mock_client_factory, mock_get_rate_limiter, preferences
):
    from core.rate_limiter import RateLimitBudgetExceeded

    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    mock_limiter = MagicMock()
    mock_limiter.acquire.side_effect = RateLimitBudgetExceeded("Daily token limit reached")
    mock_get_rate_limiter.return_value = mock_limiter

    with pytest.raises(LLMError, match="rate-limit budget exceeded"):
        get_recommendations([make_restaurant()], preferences)

    mock_client.chat.completions.create.assert_not_called()


@patch("core.llm_client._get_rate_limiter")
@patch("core.llm_client._client")
def test_successful_call_acquires_budget_and_records_actual_usage(
    mock_client_factory, mock_get_rate_limiter, preferences
):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_response(VALID_ARGS)
    mock_client_factory.return_value = mock_client
    mock_limiter = MagicMock()
    mock_get_rate_limiter.return_value = mock_limiter

    get_recommendations([make_restaurant()], preferences)

    assert mock_limiter.acquire.call_count == 1
    estimated_tokens = mock_limiter.acquire.call_args[0][0]
    mock_limiter.record_actual_tokens.assert_called_once_with(estimated_tokens, 1234)
