from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation"
    cache_dir: str = "data/cache"
    max_candidates_to_llm: int = 20
    log_level: str = "INFO"

    # Client-side enforcement of the Groq openai/gpt-oss-120b free-tier limits,
    # so we throttle/fail over to the fallback ranker instead of hitting real
    # 429s. Override via env if the plan or model changes.
    llm_requests_per_minute: int = 30
    llm_requests_per_day: int = 1000
    llm_tokens_per_minute: int = 8000
    llm_tokens_per_day: int = 200000
    llm_rate_limit_max_wait_seconds: float = 20.0

    api_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
