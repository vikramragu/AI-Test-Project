"""Manual inspection helper for the cleaned restaurant dataset.

Run with: python scripts/inspect_dataset.py
Not part of the automated test suite — for eyeballing field distributions,
null counts, and cuisine/location variety when tuning preprocessing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from data.loader import load_restaurants

pd.set_option("display.width", 160)


def main() -> None:
    df = load_restaurants()

    print(f"rows: {len(df)}")
    print()

    print("null counts:")
    print(df.isnull().sum())
    print()

    print("budget_tier distribution:")
    print(df["budget_tier"].value_counts())
    print()

    print("cost distribution:")
    print(df["cost"].describe())
    print()

    print("rating distribution:")
    print(df["rating"].describe())
    print()

    print(f"unique locations: {df['location'].nunique()}")
    print(df["location"].value_counts().head(10))
    print()

    all_cuisines = df["cuisines"].explode()
    print(f"unique cuisines: {all_cuisines.nunique()}")
    print(all_cuisines.value_counts().head(15))


if __name__ == "__main__":
    main()
