from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "AI Gateway"
    app_env: str = "development"
    debug: bool = True
    
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "ai_gateway"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()