from pydantic import BaseModel, Field


class Restaurant(BaseModel):
    name: str
    location: str
    cuisines: list[str]
    cost: float
    budget_tier: str
    rating: float
    extra_attributes: dict = Field(default_factory=dict)
