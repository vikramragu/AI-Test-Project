from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from core.llm_client import LLMError
from core.models import RecommendationResult, RecommendedRestaurant

CLEAN_COLUMNS = ["name", "location", "cuisines", "rating", "cost", "budget_tier"]

SAMPLE_ROWS = [
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
]


def make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=CLEAN_COLUMNS)


@pytest.fixture
def client():
    with patch("api.main.load_restaurants", return_value=make_df(SAMPLE_ROWS)):
        from api.main import app

        with TestClient(app) as test_client:
            yield test_client


def fake_llm_result() -> RecommendationResult:
    return RecommendationResult(
        recommendations=[
            RecommendedRestaurant(
                name="Spice Route",
                cuisine="North Indian, Chinese",
                rating=4.5,
                cost=800.0,
                explanation="Top-rated North Indian spot matching your preferences.",
            )
        ],
        summary="A great pick for North Indian food.",
        source="llm",
    )


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_available(client):
    response = client.get("/docs")

    assert response.status_code == 200


@patch("api.routes.recommendations.get_recommendations")
def test_happy_path_returns_llm_recommendations(mock_get_recommendations, client):
    mock_get_recommendations.return_value = fake_llm_result()

    response = client.post(
        "/recommendations",
        json={"location": "Koramangala", "cuisine": "North Indian", "min_rating": 4.0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "llm"
    assert body["location_matched"] is True
    assert body["relaxed_filters"] == []
    assert body["recommendations"][0]["name"] == "Spice Route"
    assert body["summary"] == "A great pick for North Indian food."


@patch("api.routes.recommendations.get_recommendations")
def test_relaxed_filters_path(mock_get_recommendations, client):
    mock_get_recommendations.return_value = fake_llm_result()

    response = client.post(
        "/recommendations",
        json={"location": "Koramangala", "cuisine": "Sushi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["location_matched"] is True
    assert body["relaxed_filters"] == ["cuisine"]


@patch("api.routes.recommendations.get_recommendations")
def test_llm_failure_falls_back(mock_get_recommendations, client):
    mock_get_recommendations.side_effect = LLMError("boom")

    response = client.post("/recommendations", json={"location": "Koramangala"})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert body["location_matched"] is True
    assert len(body["recommendations"]) == 2


def test_nonexistent_location_returns_empty_result(client):
    response = client.post("/recommendations", json={"location": "Delhi"})

    assert response.status_code == 200
    body = response.json()
    assert body["location_matched"] is False
    assert body["source"] == "none"
    assert body["recommendations"] == []


def test_missing_location_is_rejected(client):
    response = client.post("/recommendations", json={"cuisine": "North Indian"})

    assert response.status_code == 422


def test_invalid_budget_enum_is_rejected(client):
    response = client.post("/recommendations", json={"location": "Koramangala", "budget": "vip"})

    assert response.status_code == 422


def test_out_of_range_min_rating_is_rejected(client):
    response = client.post(
        "/recommendations", json={"location": "Koramangala", "min_rating": 5.5}
    )

    assert response.status_code == 422


def test_negative_min_rating_is_rejected(client):
    response = client.post(
        "/recommendations", json={"location": "Koramangala", "min_rating": -1}
    )

    assert response.status_code == 422
