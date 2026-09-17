from typing import Literal

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    location: str = Field(min_length=1)
    budget: Literal["low", "medium", "high"] | None = None
    cuisine: str | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    extra_preferences: str = Field(default="", max_length=500)


class RecommendedRestaurantResponse(BaseModel):
    name: str
    cuisine: str
    rating: float
    cost: float
    explanation: str


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendedRestaurantResponse]
    summary: str | None = None
    source: Literal["llm", "fallback", "none"]
    relaxed_filters: list[str] = Field(default_factory=list)
    location_matched: bool
