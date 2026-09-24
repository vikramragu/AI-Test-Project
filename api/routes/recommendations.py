import logging
import time
import uuid

from fastapi import APIRouter, Request

from api.models import RecommendationRequest, RecommendationResponse, RecommendedRestaurantResponse
from core.fallback import fallback_rank
from core.filter import filter_restaurants
from core.llm_client import LLMError, get_recommendations
from core.models import UserPreferences
from logging_config import request_id_var

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest, request: Request) -> RecommendationResponse:
    request_id_var.set(uuid.uuid4().hex[:8])
    start = time.monotonic()
    df = request.app.state.restaurants_df

    preferences = UserPreferences(
        location=payload.location,
        budget=payload.budget,
        cuisine=payload.cuisine,
        min_rating=payload.min_rating,
        extra_preferences=payload.extra_preferences,
    )

    # Note: filter parameters are logged here and in core.filter; the raw
    # extra_preferences text is deliberately never logged (only its length),
    # since it's free-form user input that may be considered sensitive.
    logger.info(
        "recommend request: location=%r budget=%r cuisine=%r min_rating=%r "
        "extra_preferences_len=%d",
        preferences.location,
        preferences.budget,
        preferences.cuisine,
        preferences.min_rating,
        len(preferences.extra_preferences),
    )

    filter_result = filter_restaurants(df, preferences)

    if not filter_result.location_matched:
        logger.info("recommend response: source=none (location not matched)")
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
        elapsed = time.monotonic() - start
        logger.warning(
            "LLM recommendation failed after %.2fs, using fallback ranker: %s", elapsed, exc
        )
        result = fallback_rank(filter_result.candidates, preferences)

    logger.info(
        "recommend response: source=%s recommendations=%d relaxed_filters=%s total_time=%.2fs",
        result.source,
        len(result.recommendations),
        filter_result.relaxed_filters,
        time.monotonic() - start,
    )

    return RecommendationResponse(
        recommendations=[
            RecommendedRestaurantResponse(**r.model_dump()) for r in result.recommendations
        ],
        summary=result.summary,
        source=result.source,
        relaxed_filters=filter_result.relaxed_filters,
        location_matched=True,
    )
