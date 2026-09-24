import logging

from core.models import RecommendationResult, RecommendedRestaurant, UserPreferences
from data.schema import Restaurant

logger = logging.getLogger(__name__)


def _score(restaurant: Restaurant) -> float:
    # Favor higher rating; lightly penalize higher cost so within similar
    # ratings, cheaper options rank first. Cost is scaled down so it acts as
    # a tiebreaker rather than dominating the rating signal.
    return restaurant.rating - (restaurant.cost / 1000.0)


def _explanation(restaurant: Restaurant) -> str:
    cuisine = restaurant.cuisines[0] if restaurant.cuisines else "a"
    return (
        f"Highly rated {cuisine} option in {restaurant.location} "
        f"({restaurant.rating}/5, ~{restaurant.cost:.0f} for two, {restaurant.budget_tier} budget)."
    )


def fallback_rank(
    candidates: list[Restaurant], preferences: UserPreferences
) -> RecommendationResult:
    """Deterministic, non-LLM ranking used when the LLM path fails.

    Never calls out to any external service, so it can't itself fail the
    way the LLM path can -- this is what guarantees the API always returns
    a result. Candidates are assumed to already be filtered/capped by
    core.filter.
    """
    del preferences  # not used for scoring; kept for a consistent call signature

    logger.info("fallback ranking used for %d candidates", len(candidates))

    ranked = sorted(candidates, key=_score, reverse=True)
    recommendations = [
        RecommendedRestaurant(
            name=r.name,
            cuisine=", ".join(r.cuisines),
            rating=r.rating,
            cost=r.cost,
            explanation=_explanation(r),
        )
        for r in ranked
    ]
    return RecommendationResult(recommendations=recommendations, summary=None, source="fallback")
