import os
from dataclasses import dataclass
from functools import lru_cache

EMBEDDING_DIM = 512  # must match vector(512) in the initial migration


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_base_url: str
    embedding_base_url: str
    llm_timeout_s: float
    embedding_timeout_s: float
    db_pool_max_size: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://billforge:billforge@localhost:5432/billforge"
        ),
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:8001"),
        embedding_base_url=os.environ.get("EMBEDDING_BASE_URL", "http://localhost:8002"),
        llm_timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "5")),
        embedding_timeout_s=float(os.environ.get("EMBEDDING_TIMEOUT_S", "3")),
        db_pool_max_size=int(os.environ.get("DB_POOL_MAX_SIZE", "10")),
    )
