from pathlib import Path
from unittest.mock import patch

import pytest

from data.loader import DatasetUnavailableError, load_raw_dataset


@patch("data.loader.load_dataset")
def test_no_cache_and_download_failure_raises_clear_error(mock_load_dataset, tmp_path, monkeypatch):
    from config import get_settings

    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    get_settings.cache_clear()

    mock_load_dataset.side_effect = RuntimeError("simulated network failure")

    with pytest.raises(DatasetUnavailableError) as exc_info:
        load_raw_dataset(force_refresh=True)

    message = str(exc_info.value)
    assert "simulated network failure" in message
    assert "DATASET_NAME" in message
    assert str(Path(tmp_path) / "zomato_raw.parquet") in message

    get_settings.cache_clear()
