from typing import Literal

from pydantic import BaseModel, Field

from data.schema import Restaurant


class UserPreferences(BaseModel):
    location: str
    budget: str | None = None  # "low" | "medium" | "high"
    cuisine: str | None = None
    min_rating: float | None = None
    extra_preferences: str = ""


class FilterResult(BaseModel):
    candidates: list[Restaurant]
    relaxed_filters: list[str] = Field(default_factory=list)
    location_matched: bool


class RecommendedRestaurant(BaseModel):
    name: str
    cuisine: str
    rating: float
    cost: float
    explanation: str


class RecommendationResult(BaseModel):
    recommendations: list[RecommendedRestaurant]
    summary: str | None = None
    source: Literal["llm", "fallback"]
