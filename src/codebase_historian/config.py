"""
Configuration settings for Codebase Historian.
"""

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Codebase Historian"
    version: str = "0.1.0"
    db_path: str = "historian.db"
    chroma_db_path: str = ".chroma"
    api_keys: list[str] = ["test-key-historian", "dev-key-123"]
    rate_limit_capacity: int = 60
    rate_limit_refill_rate: float = 1.0
    auth_enabled: bool = True


settings = Settings()

