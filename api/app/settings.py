from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "System Design API"
    environment: str = "development"

    # Caching
    cache_backend: str = "memory"  # "memory" or "redis"
    cache_ttl_seconds: int = 60
    redis_url: Optional[str] = None  # e.g. redis://localhost:6379/0

    # Queue
    queue_worker_concurrency: int = 2

    # Security / TLS hints
    enforce_https: bool = True
    hsts_max_age: int = 31536000  # 1 year

    class Config:
        env_prefix = "APP_"
        case_sensitive = False


settings = Settings()
