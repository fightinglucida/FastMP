from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project metadata
    PROJECT_NAME: str = "WeChat Article Collector API"
    VERSION: str = "0.1.0"

    # Environment
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = True

    # Security / CORS
    BACKEND_CORS_ORIGINS: List[str] = []

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"  # can be overwritten by env

    # Auth / JWT
    JWT_SECRET: str = "change-this-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
