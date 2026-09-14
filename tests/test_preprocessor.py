import pandas as pd

from data.preprocessor import preprocess, to_restaurants

RAW_COLUMNS = [
    "name",
    "location",
    "cuisines",
    "rate",
    "approx_cost(for two people)",
    "address",
    "rest_type",
    "dish_liked",
    "votes",
    "online_order",
    "book_table",
]


def make_raw_row(**overrides) -> dict:
    row = {
        "name": "Jalsa",
        "location": "Banashankari",
        "cuisines": "North Indian, Mughlai, Chinese",
        "rate": "4.1/5",
        "approx_cost(for two people)": "800",
        "address": "942, 21st Main Road, Banashankari",
        "rest_type": "Casual Dining",
        "dish_liked": "Biryani",
        "votes": "775",
        "online_order": "Yes",
        "book_table": "No",
    }
    row.update(overrides)
    return row


def make_raw_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def test_valid_row_is_parsed_correctly():
    df = make_raw_df([make_raw_row()])
    clean = preprocess(df)

    assert len(clean) == 1
    row = clean.iloc[0]
    assert row["name"] == "Jalsa"
    assert row["cuisines"] == ["North Indian", "Mughlai", "Chinese"]
    assert row["cost"] == 800.0
    assert row["rating"] == 4.1
    assert row["budget_tier"] == "high"


def test_cost_with_thousands_separator_is_parsed():
    df = make_raw_df([make_raw_row(**{"approx_cost(for two people)": "1,200"})])
    clean = preprocess(df)

    assert clean.iloc[0]["cost"] == 1200.0
    assert clean.iloc[0]["budget_tier"] == "high"


def test_rating_with_extra_whitespace_is_parsed():
    df = make_raw_df([make_raw_row(rate="3.8 /5")])
    clean = preprocess(df)

    assert clean.iloc[0]["rating"] == 3.8


def test_missing_cost_row_is_dropped():
    df = make_raw_df([make_raw_row(**{"approx_cost(for two people)": None})])
    clean = preprocess(df)

    assert len(clean) == 0


def test_non_numeric_rating_row_is_dropped():
    for placeholder in ["NEW", "-"]:
        df = make_raw_df([make_raw_row(rate=placeholder)])
        clean = preprocess(df)
        assert len(clean) == 0, f"expected row with rate={placeholder!r} to be dropped"


def test_missing_rating_row_is_dropped():
    df = make_raw_df([make_raw_row(rate=None)])
    clean = preprocess(df)

    assert len(clean) == 0


def test_empty_cuisine_row_is_dropped():
    df = make_raw_df([make_raw_row(cuisines=None)])
    clean = preprocess(df)

    assert len(clean) == 0


def test_budget_tier_boundaries():
    df = make_raw_df(
        [
            make_raw_row(name="Low", **{"approx_cost(for two people)": "300"}),
            make_raw_row(name="Medium", **{"approx_cost(for two people)": "301"}),
            make_raw_row(name="MediumHigh", **{"approx_cost(for two people)": "700"}),
            make_raw_row(name="High", **{"approx_cost(for two people)": "701"}),
        ]
    )
    clean = preprocess(df).set_index("name")

    assert clean.loc["Low", "budget_tier"] == "low"
    assert clean.loc["Medium", "budget_tier"] == "medium"
    assert clean.loc["MediumHigh", "budget_tier"] == "medium"
    assert clean.loc["High", "budget_tier"] == "high"


def test_duplicate_rows_are_deduplicated_by_name_and_address():
    df = make_raw_df(
        [
            make_raw_row(),
            make_raw_row(),
            make_raw_row(rest_type="Delivery"),
        ]
    )
    clean = preprocess(df)

    assert len(clean) == 1


def test_same_name_different_address_is_not_deduplicated():
    df = make_raw_df(
        [
            make_raw_row(address="Branch A, Koramangala"),
            make_raw_row(address="Branch B, Indiranagar"),
        ]
    )
    clean = preprocess(df)

    assert len(clean) == 2


def test_to_restaurants_builds_valid_schema_objects():
    df = make_raw_df([make_raw_row()])
    clean = preprocess(df)
    restaurants = to_restaurants(clean)

    assert len(restaurants) == 1
    restaurant = restaurants[0]
    assert restaurant.name == "Jalsa"
    assert restaurant.cuisines == ["North Indian", "Mughlai", "Chinese"]
    assert restaurant.budget_tier == "high"
    assert restaurant.extra_attributes["rest_type"] == "Casual Dining"
