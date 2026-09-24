import logging

import pandas as pd

from config import get_settings
from core.models import FilterResult, UserPreferences
from data.preprocessor import to_restaurants

logger = logging.getLogger(__name__)


def _filter_by_budget(df: pd.DataFrame, budget: str | None) -> pd.DataFrame:
    if not budget:
        return df
    return df[df["budget_tier"].str.casefold() == budget.strip().casefold()]


def _filter_by_cuisine(df: pd.DataFrame, cuisine: str | None) -> pd.DataFrame:
    if not cuisine or not cuisine.strip():
        return df
    target = cuisine.strip().casefold()
    # Substring match, not exact-token: the dataset has no bare "Indian"
    # entry, only "North Indian" / "South Indian" / etc., so a broad query
    # like "Indian" should still match those rather than returning nothing.
    mask = df["cuisines"].apply(lambda cuisines: any(target in c.casefold() for c in cuisines))
    return df[mask]


def _filter_by_rating(df: pd.DataFrame, min_rating: float | None) -> pd.DataFrame:
    if min_rating is None:
        return df
    return df[df["rating"] >= min_rating]


def _sort_and_cap(df: pd.DataFrame, max_candidates: int) -> pd.DataFrame:
    return df.sort_values(
        by=["rating", "cost", "name"], ascending=[False, True, True], kind="stable"
    ).head(max_candidates)


def filter_restaurants(
    df: pd.DataFrame,
    preferences: UserPreferences,
    max_candidates: int | None = None,
) -> FilterResult:
    """Apply hard filters, then progressively relax on zero matches.

    Location is never relaxed: a location that matches nothing in the
    dataset is a distinct terminal state (location_matched=False), not
    something to work around by broadening other filters. Once location
    matches at least one restaurant, the returned candidate list is
    guaranteed non-empty (relaxation bottoms out at "everything in this
    location").
    """
    max_candidates = max_candidates or get_settings().max_candidates_to_llm

    location = (preferences.location or "").strip().casefold()
    working = df if not location else df[df["location"].str.casefold() == location]

    if working.empty:
        logger.info(
            "filter: location=%r not matched in dataset (0 rows)", preferences.location
        )
        return FilterResult(candidates=[], relaxed_filters=[], location_matched=False)

    relaxed: list[str] = []

    candidates = _filter_by_rating(
        _filter_by_budget(_filter_by_cuisine(working, preferences.cuisine), preferences.budget),
        preferences.min_rating,
    )

    if candidates.empty and preferences.cuisine:
        relaxed.append("cuisine")
        candidates = _filter_by_rating(
            _filter_by_budget(working, preferences.budget), preferences.min_rating
        )

    if candidates.empty and preferences.budget:
        relaxed.append("budget")
        candidates = _filter_by_rating(working, preferences.min_rating)

    if candidates.empty and preferences.min_rating is not None:
        relaxed.append("rating")
        candidates = working

    candidates = _sort_and_cap(candidates, max_candidates)

    logger.info(
        "filter: location=%r budget=%r cuisine=%r min_rating=%r -> candidates=%d relaxed=%s",
        preferences.location,
        preferences.budget,
        preferences.cuisine,
        preferences.min_rating,
        len(candidates),
        relaxed,
    )

    return FilterResult(
        candidates=to_restaurants(candidates),
        relaxed_filters=relaxed,
        location_matched=True,
    )
