import logging

from fastapi import APIRouter, Request

from api.models import RecommendationRequest, RecommendationResponse, RecommendedRestaurantResponse
from core.fallback import fallback_rank
from core.filter import filter_restaurants
from core.llm_client import LLMError, get_recommendations
from core.models import UserPreferences

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest, request: Request) -> RecommendationResponse:
    df = request.app.state.restaurants_df

    preferences = UserPreferences(
        location=payload.location,
        budget=payload.budget,
        cuisine=payload.cuisine,
        min_rating=payload.min_rating,
        extra_preferences=payload.extra_preferences,
    )

    filter_result = filter_restaurants(df, preferences)

    if not filter_result.location_matched:
        return RecommendationResponse(
            recommendations=[],
            summary=None,
            source="none",
            relaxed_filters=[],
            location_matched=False,
        )

    try:
        result = get_recommendations(filter_result.candidates, preferences)
    except LLMError as exc:
        logger.warning("LLM recommendation failed, using fallback ranker: %s", exc)
        result = fallback_rank(filter_result.candidates, preferences)

    return RecommendationResponse(
        recommendations=[
            RecommendedRestaurantResponse(**r.model_dump()) for r in result.recommendations
        ],
        summary=result.summary,
        source=result.source,
        relaxed_filters=filter_result.relaxed_filters,
        location_matched=True,
    )
