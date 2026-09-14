import ftfy
import pandas as pd

from data.schema import Restaurant

# Derived from inspecting approx_cost(for two people) on the raw dataset:
# 25th percentile ~300, median ~400, 75th percentile ~650. Rounded to give
# three roughly usable budget tiers rather than exact quantile cutoffs.
BUDGET_LOW_MAX = 300.0
BUDGET_MEDIUM_MAX = 700.0

# Maps raw Hugging Face dataset columns to canonical names. Also acts as the
# set of columns preprocess() operates on; any other raw column is dropped.
RAW_COLUMNS = {
    "name": "name",
    "location": "location",
    "cuisines": "cuisines",
    "rate": "rating",
    "approx_cost(for two people)": "cost",
    "address": "address",
    "rest_type": "rest_type",
    "dish_liked": "dish_liked",
    "votes": "votes",
    "online_order": "online_order",
    "book_table": "book_table",
}

EXTRA_ATTRIBUTE_COLUMNS = [
    "rest_type",
    "dish_liked",
    "votes",
    "online_order",
    "book_table",
    "address",
]


def _budget_tier(cost: float) -> str:
    if cost <= BUDGET_LOW_MAX:
        return "low"
    if cost <= BUDGET_MEDIUM_MAX:
        return "medium"
    return "high"


def _split_cuisines(value: object) -> list[str] | None:
    if not isinstance(value, str):
        return None
    cuisines = [c.strip() for c in value.split(",") if c.strip()]
    return cuisines or None


def preprocess(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw Zomato dataset into a canonical restaurant table.

    Drops any row missing a usable name, location, cuisine, cost, or rating,
    since filtering and prompting downstream require all of these fields.
    Also collapses duplicate rows: the raw dataset repeats each restaurant
    once per `listed_in(type)` category (Buffet/Delivery/Dine-out/...), all
    sharing the same name+address, so those are deduplicated to one row.
    """
    df = raw_df.rename(columns=RAW_COLUMNS)[list(RAW_COLUMNS.values())].copy()

    # A small fraction of names in the raw dataset are mojibake (multiply
    # re-encoded UTF-8, e.g. "SantÃÂÃÂ..." for "Santé") — ftfy repairs most
    # of it; any residual garbling is a pre-existing source-data defect.
    df["name"] = df["name"].apply(ftfy.fix_text).str.strip()
    df["location"] = df["location"].str.strip()
    df["cuisines"] = df["cuisines"].apply(_split_cuisines)

    df["cost"] = pd.to_numeric(df["cost"].str.replace(",", "", regex=False), errors="coerce")
    df["rating"] = pd.to_numeric(
        df["rating"].str.extract(r"(\d+\.?\d*)", expand=False), errors="coerce"
    )

    df = df.dropna(subset=["name", "location", "cost", "rating"])
    # .notna() (not .apply(isinstance...)) so the mask is always bool dtype;
    # an apply-derived mask on a 0-row frame comes back as dtype=object and
    # silently drops all columns instead of filtering rows when applied.
    df = df[df["cuisines"].notna()]
    df = df[(df["name"] != "") & (df["location"] != "")]
    df = df[(df["cost"] > 0) & df["rating"].between(0, 5)]

    df["budget_tier"] = df["cost"].apply(_budget_tier)

    df = df.drop_duplicates(subset=["name", "address"], keep="first")

    return df.reset_index(drop=True)


def to_restaurants(df: pd.DataFrame) -> list[Restaurant]:
    restaurants = []
    for row in df.to_dict(orient="records"):
        extra_attributes = {
            key: row[key] for key in EXTRA_ATTRIBUTE_COLUMNS if key in row and pd.notna(row[key])
        }
        restaurants.append(
            Restaurant(
                name=row["name"],
                location=row["location"],
                cuisines=list(row["cuisines"]),
                cost=row["cost"],
                budget_tier=row["budget_tier"],
                rating=row["rating"],
                extra_attributes=extra_attributes,
            )
        )
    return restaurants
