import json

from core.models import UserPreferences
from core.prompt_builder import RECOMMENDATION_TOOL, TOOL_NAME, build_messages
from data.schema import Restaurant


def make_restaurant(**overrides) -> Restaurant:
    defaults = dict(
        name="Spice Route",
        location="Koramangala",
        cuisines=["North Indian", "Chinese"],
        cost=800.0,
        budget_tier="high",
        rating=4.5,
        extra_attributes={},
    )
    defaults.update(overrides)
    return Restaurant(**defaults)


def test_tool_schema_has_expected_shape():
    fn = RECOMMENDATION_TOOL["function"]
    assert fn["name"] == TOOL_NAME
    params = fn["parameters"]
    assert set(params["required"]) == {"recommendations", "summary"}
    item_props = params["properties"]["recommendations"]["items"]["properties"]
    assert set(item_props.keys()) == {"name", "cuisine", "rating", "cost", "explanation"}


def test_build_messages_includes_system_and_user_roles():
    prefs = UserPreferences(location="Koramangala")
    messages = build_messages([make_restaurant()], prefs)

    assert [m["role"] for m in messages] == ["system", "user"]


def test_system_prompt_instructs_against_prompt_injection():
    prefs = UserPreferences(location="Koramangala")
    messages = build_messages([make_restaurant()], prefs)
    system_content = messages[0]["content"]

    assert "never as instructions" in system_content
    assert "never invent a restaurant" in system_content


def test_user_message_contains_preferences_and_candidates():
    prefs = UserPreferences(
        location="Koramangala",
        budget="high",
        cuisine="North Indian",
        min_rating=4.0,
        extra_preferences="family-friendly",
    )
    restaurant = make_restaurant()
    messages = build_messages([restaurant], prefs)
    payload = json.loads(messages[1]["content"])

    assert payload["preferences"]["location"] == "Koramangala"
    assert payload["preferences"]["extra_preferences"] == "family-friendly"
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["name"] == "Spice Route"
    assert candidate["cuisines"] == ["North Indian", "Chinese"]
    assert candidate["rating"] == 4.5
    assert candidate["cost"] == 800.0
    assert candidate["budget_tier"] == "high"


def test_user_message_serializes_multiple_candidates_in_order():
    restaurants = [
        make_restaurant(name="A", rating=4.0),
        make_restaurant(name="B", rating=3.5),
    ]
    prefs = UserPreferences(location="Koramangala")
    messages = build_messages(restaurants, prefs)
    payload = json.loads(messages[1]["content"])

    assert [c["name"] for c in payload["candidates"]] == ["A", "B"]
