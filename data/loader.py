from pathlib import Path

import pandas as pd
from datasets import load_dataset

from config import get_settings
from data.preprocessor import preprocess

RAW_CACHE_FILENAME = "zomato_raw.parquet"
CLEAN_CACHE_FILENAME = "zomato_clean.parquet"


def _cache_dir() -> Path:
    path = Path(get_settings().cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_raw_dataset(force_refresh: bool = False) -> pd.DataFrame:
    """Load the raw Zomato dataset, caching it locally as Parquet.

    Subsequent calls read from the local cache instead of re-downloading
    from Hugging Face, unless force_refresh is set.
    """
    cache_path = _cache_dir() / RAW_CACHE_FILENAME

    if cache_path.exists() and not force_refresh:
        return pd.read_parquet(cache_path)

    settings = get_settings()
    dataset = load_dataset(settings.dataset_name)["train"]
    df = dataset.to_pandas()
    df.to_parquet(cache_path, index=False)
    return df


def load_restaurants(force_refresh: bool = False) -> pd.DataFrame:
    """Load and clean the dataset, caching the cleaned result separately.

    Returns a flat DataFrame (not a list of Restaurant objects) since the
    filtering engine (Phase 2) operates on the DataFrame directly for
    performance; use data.preprocessor.to_restaurants() to convert rows to
    the canonical Restaurant schema when needed.
    """
    cache_path = _cache_dir() / CLEAN_CACHE_FILENAME

    if cache_path.exists() and not force_refresh:
        df = pd.read_parquet(cache_path)
        df["cuisines"] = df["cuisines"].apply(list)
        return df

    raw_df = load_raw_dataset(force_refresh=force_refresh)
    clean_df = preprocess(raw_df)
    clean_df.to_parquet(cache_path, index=False)
    return clean_df
