from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"
    dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation"
    cache_dir: str = "data/cache"
    max_candidates_to_llm: int = 20
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
