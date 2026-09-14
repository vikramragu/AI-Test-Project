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
