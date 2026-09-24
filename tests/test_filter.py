import pandas as pd
import pytest

from core.filter import filter_restaurants
from core.models import UserPreferences

CLEAN_COLUMNS = ["name", "location", "cuisines", "rating", "cost", "budget_tier"]


def make_clean_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=CLEAN_COLUMNS)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return make_clean_df(
        [
            {
                "name": "Spice Route",
                "location": "Koramangala",
                "cuisines": ["North Indian", "Chinese"],
                "rating": 4.5,
                "cost": 800.0,
                "budget_tier": "high",
            },
            {
                "name": "Curry Leaf",
                "location": "Koramangala",
                "cuisines": ["South Indian"],
                "rating": 4.2,
                "cost": 300.0,
                "budget_tier": "low",
            },
            {
                "name": "Pasta Palace",
                "location": "Koramangala",
                "cuisines": ["Italian"],
                "rating": 3.9,
                "cost": 500.0,
                "budget_tier": "medium",
            },
            {
                "name": "Budget Bites",
                "location": "Koramangala",
                "cuisines": ["Fast Food"],
                "rating": 3.5,
                "cost": 200.0,
                "budget_tier": "low",
            },
            {
                "name": "Indiranagar Grill",
                "location": "Indiranagar",
                "cuisines": ["North Indian", "Continental"],
                "rating": 4.0,
                "cost": 900.0,
                "budget_tier": "high",
            },
        ]
    )


def test_exact_match_returns_filtered_sorted_candidates(sample_df):
    prefs = UserPreferences(location="Koramangala", cuisine="North Indian")
    result = filter_restaurants(sample_df, prefs)

    assert result.location_matched is True
    assert result.relaxed_filters == []
    assert [r.name for r in result.candidates] == ["Spice Route"]


def test_location_matching_is_case_insensitive(sample_df):
    prefs = UserPreferences(location="  koramangala  ")
    result = filter_restaurants(sample_df, prefs)

    assert result.location_matched is True
    assert len(result.candidates) == 4


def test_nonexistent_location_is_not_matched_and_not_relaxed(sample_df):
    prefs = UserPreferences(location="Delhi", cuisine="North Indian")
    result = filter_restaurants(sample_df, prefs)

    assert result.location_matched is False
    assert result.candidates == []
    assert result.relaxed_filters == []


def test_cuisine_substring_match(sample_df):
    prefs = UserPreferences(location="Koramangala", cuisine="Indian")
    result = filter_restaurants(sample_df, prefs)

    names = {r.name for r in result.candidates}
    assert names == {"Spice Route", "Curry Leaf"}


def test_nonexistent_cuisine_relaxes_cuisine_only(sample_df):
    prefs = UserPreferences(location="Koramangala", cuisine="Sushi", budget="low")
    result = filter_restaurants(sample_df, prefs)

    assert result.location_matched is True
    assert result.relaxed_filters == ["cuisine"]
    names = {r.name for r in result.candidates}
    assert names == {"Curry Leaf", "Budget Bites"}


def test_impossible_cuisine_and_budget_relaxes_both_in_order():
    df = make_clean_df(
        [
            {
                "name": "Curry Leaf",
                "location": "Koramangala",
                "cuisines": ["South Indian"],
                "rating": 4.2,
                "cost": 300.0,
                "budget_tier": "low",
            },
            {
                "name": "Pasta Palace",
                "location": "Koramangala",
                "cuisines": ["Italian"],
                "rating": 3.9,
                "cost": 500.0,
                "budget_tier": "medium",
            },
        ]
    )
    # Nothing in this location is "high" budget, so relaxing cuisine alone
    # still yields zero matches and budget must be relaxed too.
    prefs = UserPreferences(location="Koramangala", cuisine="Sushi", budget="high")
    result = filter_restaurants(df, prefs)

    assert result.relaxed_filters == ["cuisine", "budget"]
    assert len(result.candidates) == 2


def test_min_rating_above_max_relaxes_rating_last(sample_df):
    prefs = UserPreferences(location="Koramangala", min_rating=4.9)
    result = filter_restaurants(sample_df, prefs)

    assert result.relaxed_filters == ["rating"]
    assert len(result.candidates) == 4


def test_min_rating_boundary_is_inclusive(sample_df):
    prefs = UserPreferences(location="Koramangala", min_rating=4.2)
    result = filter_restaurants(sample_df, prefs)

    names = {r.name for r in result.candidates}
    assert names == {"Spice Route", "Curry Leaf"}


def test_no_optional_filters_returns_full_location_set(sample_df):
    prefs = UserPreferences(location="Koramangala")
    result = filter_restaurants(sample_df, prefs)

    assert result.relaxed_filters == []
    assert len(result.candidates) == 4


def test_results_sorted_by_rating_desc_then_cost_asc(sample_df):
    prefs = UserPreferences(location="Koramangala")
    result = filter_restaurants(sample_df, prefs)

    ratings = [r.rating for r in result.candidates]
    assert ratings == sorted(ratings, reverse=True)


def test_deterministic_tiebreak_by_name_when_rating_and_cost_match():
    df = make_clean_df(
        [
            {
                "name": "Zeta Diner",
                "location": "HSR",
                "cuisines": ["Cafe"],
                "rating": 4.0,
                "cost": 400.0,
                "budget_tier": "medium",
            },
            {
                "name": "Alpha Diner",
                "location": "HSR",
                "cuisines": ["Cafe"],
                "rating": 4.0,
                "cost": 400.0,
                "budget_tier": "medium",
            },
        ]
    )
    prefs = UserPreferences(location="HSR")
    result = filter_restaurants(df, prefs)

    assert [r.name for r in result.candidates] == ["Alpha Diner", "Zeta Diner"]


def test_candidate_cap_is_enforced():
    rows = [
        {
            "name": f"Restaurant {i}",
            "location": "HSR",
            "cuisines": ["Cafe"],
            "rating": 3.0 + (i % 20) * 0.05,
            "cost": 300.0,
            "budget_tier": "low",
        }
        for i in range(30)
    ]
    df = make_clean_df(rows)
    prefs = UserPreferences(location="HSR")

    result = filter_restaurants(df, prefs, max_candidates=15)

    assert len(result.candidates) == 15
    ratings = [r.rating for r in result.candidates]
    assert ratings == sorted(ratings, reverse=True)


def test_candidate_cap_is_enforced_even_after_full_relaxation():
    # A large pool where cuisine, budget, and rating all get relaxed --
    # the cap must still apply to the final (fully relaxed) candidate set,
    # not just the unfiltered case, since relaxation runs before the cap.
    rows = [
        {
            "name": f"Restaurant {i}",
            "location": "HSR",
            "cuisines": ["Cafe"],
            "rating": 3.0 + (i % 20) * 0.05,
            "cost": 300.0,
            "budget_tier": "low",
        }
        for i in range(30)
    ]
    df = make_clean_df(rows)
    prefs = UserPreferences(
        location="HSR", cuisine="Sushi", budget="high", min_rating=4.9
    )

    result = filter_restaurants(df, prefs, max_candidates=15)

    assert result.relaxed_filters == ["cuisine", "budget", "rating"]
    assert len(result.candidates) == 15
    ratings = [r.rating for r in result.candidates]
    assert ratings == sorted(ratings, reverse=True)
