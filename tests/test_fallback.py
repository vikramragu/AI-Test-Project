from core.fallback import fallback_rank
from core.models import UserPreferences
from data.schema import Restaurant


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


def test_fallback_never_touches_network_and_returns_fallback_source():
    result = fallback_rank([make_restaurant()], UserPreferences(location="Koramangala"))

    assert result.source == "fallback"
    assert len(result.recommendations) == 1


def test_higher_rating_ranks_first_at_similar_cost():
    high = make_restaurant(name="High Rated", rating=4.8, cost=500.0)
    low = make_restaurant(name="Low Rated", rating=3.5, cost=500.0)

    result = fallback_rank([low, high], UserPreferences(location="Koramangala"))

    assert [r.name for r in result.recommendations] == ["High Rated", "Low Rated"]


def test_cheaper_option_breaks_ties_at_similar_rating():
    expensive = make_restaurant(name="Expensive", rating=4.0, cost=2000.0)
    cheap = make_restaurant(name="Cheap", rating=4.0, cost=200.0)

    result = fallback_rank([expensive, cheap], UserPreferences(location="Koramangala"))

    assert [r.name for r in result.recommendations] == ["Cheap", "Expensive"]


def test_explanations_are_populated_and_non_empty():
    result = fallback_rank([make_restaurant()], UserPreferences(location="Koramangala"))

    assert result.recommendations[0].explanation
    assert "Koramangala" in result.recommendations[0].explanation


def test_empty_candidates_returns_empty_recommendations():
    result = fallback_rank([], UserPreferences(location="Koramangala"))

    assert result.source == "fallback"
    assert result.recommendations == []
