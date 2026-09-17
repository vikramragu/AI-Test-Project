from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from streamlit.testing.v1 import AppTest

from frontend.app import BUDGET_ANY, build_payload, fetch_recommendations

APP_PATH = str(Path(__file__).resolve().parent.parent / "frontend" / "app.py")


def make_json_response(data: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


SUCCESS_DATA = {
    "recommendations": [
        {
            "name": "Spice Route",
            "cuisine": "North Indian",
            "rating": 4.5,
            "cost": 800.0,
            "explanation": "Great pick for your preferences.",
        }
    ],
    "summary": "A solid choice for North Indian food.",
    "source": "llm",
    "relaxed_filters": [],
    "location_matched": True,
}


# --- build_payload -----------------------------------------------------


def test_build_payload_minimal_omits_optional_fields():
    payload = build_payload(
        location="Koramangala",
        budget=BUDGET_ANY,
        cuisine="",
        min_rating=0.0,
        extra_preferences="",
    )

    assert payload == {"location": "Koramangala", "extra_preferences": ""}


def test_build_payload_includes_all_provided_fields():
    payload = build_payload(
        location="  Koramangala  ",
        budget="medium",
        cuisine=" Italian ",
        min_rating=4.0,
        extra_preferences=" family-friendly ",
    )

    assert payload == {
        "location": "Koramangala",
        "budget": "medium",
        "cuisine": "Italian",
        "min_rating": 4.0,
        "extra_preferences": "family-friendly",
    }


# --- fetch_recommendations ----------------------------------------------


@patch("frontend.app.httpx.post")
def test_fetch_recommendations_success(mock_post):
    mock_post.return_value = make_json_response(SUCCESS_DATA)

    result = fetch_recommendations({"location": "Koramangala", "extra_preferences": ""})

    assert result == {"ok": True, "data": SUCCESS_DATA}


@patch("frontend.app.httpx.post")
def test_fetch_recommendations_connect_error(mock_post):
    mock_post.side_effect = httpx.ConnectError("connection refused")

    result = fetch_recommendations({"location": "Koramangala", "extra_preferences": ""})

    assert result["ok"] is False
    assert "running" in result["error"]


@patch("frontend.app.httpx.post")
def test_fetch_recommendations_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timed out")

    result = fetch_recommendations({"location": "Koramangala", "extra_preferences": ""})

    assert result["ok"] is False
    assert "too long" in result["error"]


@patch("frontend.app.httpx.post")
def test_fetch_recommendations_http_status_error(mock_post):
    request = httpx.Request("POST", "http://localhost:8000/recommendations")
    response = httpx.Response(status_code=422, request=request, text="Invalid request body")
    mock_post.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=httpx.HTTPStatusError("bad request", request=request, response=response)
        )
    )

    result = fetch_recommendations({"location": "Koramangala", "extra_preferences": ""})

    assert result["ok"] is False
    assert "422" in result["error"]


# --- Full form flow via Streamlit AppTest --------------------------------
#
# Patching must target the shared `httpx.post` attribute, not
# `frontend.app.httpx.post`: AppTest execs the script into its own isolated
# module context rather than reusing whatever `import frontend.app` (the
# patch target resolution) puts in sys.modules, so a patch scoped to
# `frontend.app` never reaches AppTest's execution. `httpx` itself is a
# single shared module either way, so patching its `post` attribute
# directly is what actually intercepts the call.


def test_initial_render_has_no_exception():
    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert [ti.label for ti in at.text_input] == ["Location", "Cuisine (optional)"]
    assert at.button[0].label == "Find Restaurants"


def test_empty_location_shows_error_without_calling_backend():
    with patch("httpx.post") as mock_post:
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.button[0].click().run()

    assert not at.exception
    assert any("Please enter a location" in e.value for e in at.error)
    mock_post.assert_not_called()


def test_happy_path_renders_recommendation_card():
    with patch("httpx.post", return_value=make_json_response(SUCCESS_DATA)):
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("Koramangala").run()
        at.button[0].click().run()

    assert not at.exception
    assert at.subheader[0].value == "Spice Route"
    assert any("A solid choice" in m.value for m in at.markdown)
    assert not at.warning  # no relaxed/fallback/no-match banners on the happy path


def test_relaxed_filters_shows_info_banner():
    data = {**SUCCESS_DATA, "relaxed_filters": ["cuisine"]}
    with patch("httpx.post", return_value=make_json_response(data)):
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("Koramangala").run()
        at.button[0].click().run()

    assert not at.exception
    assert any("cuisine" in i.value for i in at.info)
    assert at.subheader[0].value == "Spice Route"


def test_fallback_source_shows_warning_banner():
    data = {**SUCCESS_DATA, "source": "fallback", "summary": None}
    with patch("httpx.post", return_value=make_json_response(data)):
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("Koramangala").run()
        at.button[0].click().run()

    assert not at.exception
    assert any("temporarily unavailable" in w.value for w in at.warning)
    assert at.subheader[0].value == "Spice Route"


def test_no_location_match_shows_warning_and_no_cards():
    data = {
        "recommendations": [],
        "summary": None,
        "source": "none",
        "relaxed_filters": [],
        "location_matched": False,
    }
    with patch("httpx.post", return_value=make_json_response(data)):
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("Delhi").run()
        at.button[0].click().run()

    assert not at.exception
    assert any("Bangalore neighborhoods" in w.value for w in at.warning)
    assert not at.subheader


def test_backend_unreachable_shows_error():
    with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("Koramangala").run()
        at.button[0].click().run()

    assert not at.exception
    assert any("running" in e.value for e in at.error)
    assert not at.subheader
