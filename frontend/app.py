import httpx
import streamlit as st

from config import get_settings

BUDGET_ANY = "Any"
BUDGET_OPTIONS = [BUDGET_ANY, "low", "medium", "high"]
REQUEST_TIMEOUT_SECONDS = 40.0


def build_payload(
    location: str,
    budget: str,
    cuisine: str,
    min_rating: float,
    extra_preferences: str,
) -> dict:
    payload: dict = {
        "location": location.strip(),
        "extra_preferences": extra_preferences.strip(),
    }
    if cuisine.strip():
        payload["cuisine"] = cuisine.strip()
    if budget != BUDGET_ANY:
        payload["budget"] = budget
    if min_rating > 0:
        payload["min_rating"] = min_rating
    return payload


def fetch_recommendations(payload: dict) -> dict:
    """Calls the backend. Never raises -- always returns a result dict so
    the caller can render something to the user instead of crashing the
    page on a network error."""
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.api_base_url}/recommendations",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except httpx.ConnectError:
        return {
            "ok": False,
            "error": (
                "Couldn't reach the recommendation service. Make sure the API is "
                "running (`uvicorn api.main:app`)."
            ),
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "error": "The recommendation service took too long to respond. Please try again.",
        }
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "error": f"Request failed ({exc.response.status_code}): {exc.response.text}",
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Request failed: {exc}"}


def render_results(data: dict) -> None:
    if not data["location_matched"]:
        st.warning(
            "We couldn't find any restaurants for that location in our dataset. "
            "This dataset only covers Bangalore neighborhoods (e.g. Koramangala, "
            "Indiranagar, Whitefield, HSR, Jayanagar) -- try one of those."
        )
        return

    if data["relaxed_filters"]:
        relaxed = ", ".join(data["relaxed_filters"])
        st.info(
            f"We couldn't find matches for all your filters, so we relaxed: **{relaxed}**. "
            "Here are the closest matches instead."
        )

    if data["source"] == "fallback":
        st.warning(
            "Our AI recommender is temporarily unavailable, so these results are "
            "ranked by rating and cost rather than personally explained."
        )

    recommendations = data["recommendations"]
    if not recommendations:
        st.info("No restaurants matched your preferences.")
        return

    if data.get("summary"):
        st.markdown(f"**{data['summary']}**")

    for restaurant in recommendations:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(restaurant["name"])
                st.caption(restaurant["cuisine"])
            with col2:
                st.metric("Rating", f"{restaurant['rating']:.1f} / 5")
            st.write(f"Approx. {restaurant['cost']:.0f} for two")
            st.write(restaurant["explanation"])


def main() -> None:
    st.set_page_config(page_title="Restaurant Recommendations", page_icon=":fork_and_knife:")

    st.title("Restaurant Recommendations")
    st.caption(
        "Tell us what you're looking for and we'll find the best matches "
        "(Bangalore neighborhoods only -- e.g. Koramangala, Indiranagar, Whitefield)."
    )

    with st.form("preferences_form"):
        location = st.text_input("Location", placeholder="e.g. Koramangala")
        col1, col2 = st.columns(2)
        with col1:
            budget = st.selectbox("Budget", options=BUDGET_OPTIONS)
        with col2:
            min_rating = st.slider("Minimum rating", 0.0, 5.0, 0.0, 0.1)
        cuisine = st.text_input("Cuisine (optional)", placeholder="e.g. Italian, North Indian")
        extra_preferences = st.text_area(
            "Anything else? (optional)",
            placeholder="e.g. family-friendly, quick service, outdoor seating",
            max_chars=500,
        )
        submitted = st.form_submit_button("Find Restaurants")

    if not submitted:
        return

    if not location.strip():
        st.error("Please enter a location.")
        return

    payload = build_payload(location, budget, cuisine, min_rating, extra_preferences)
    with st.spinner("Finding the best restaurants for you..."):
        result = fetch_recommendations(payload)

    if not result["ok"]:
        st.error(result["error"])
        return

    render_results(result["data"])


if __name__ == "__main__":
    main()
