from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ml-network-monitor"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/ml_network_monitor"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production-super-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    model_path: str = "./models/active_model.keras"
    default_threshold: float = 0.18

    model_dir: str = "./models"
    training_data_dir: str = "./training_data"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
