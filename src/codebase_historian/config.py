"""
Configuration settings for Codebase Historian.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Codebase Historian"
    version: str = "0.1.0"
    db_path: str = "historian.db"
    chroma_db_path: str = ".chroma"
    api_keys: list[str] = ["test-key-historian", "dev-key-123"]
    rate_limit_capacity: int = 60
    rate_limit_refill_rate: float = 1.0
    auth_enabled: bool = True

    # External LLM & Hugging Face credentials
    groq_api_key: str | None = None
    hf_token: str | None = None
    huggingface_hub_token: str | None = None
    llm_model: str = "openai/gpt-oss-120b"


settings = Settings()

