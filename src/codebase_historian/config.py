"""
Configuration settings for Codebase Historian.
"""

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Codebase Historian"
    version: str = "0.1.0"
    db_path: str = "historian.db"
    chroma_db_path: str = ".chroma"


settings = Settings()
