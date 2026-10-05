from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    app_name: str = "ml-network-monitor"
    app_version: str = "0.1.0"
    environment: str = "development"
    postgres_user: str = "postgres"
    postgres_password: str = "local-dev-only"
    postgres_db: str = "ml_network_monitor"
    redis_url: str = "redis://localhost:6379/0"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/ml_network_monitor"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    model_path: str = "./models/tls_64byte_dropout_autoencoder.keras"
    default_threshold: float = Field(default=0.18, ge=0)
    threshold_percentile: float = Field(default=99.0, ge=50, lt=100)

    model_dir: str = "./models"
    training_data_dir: str = "./training_data"
    zeek_host: str = "0.0.0.0"
    zeek_port: int = Field(default=9999, ge=1, le=65535)
    zeek_shared_token: str = ""
    zeek_interface: str = ""
    training_epochs: int = Field(default=50, ge=1, le=500)
    training_batch_size: int = Field(default=64, ge=1, le=4096)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32 or value.startswith(("replace-with-", "change-me-")):
            raise ValueError("SECRET_KEY must be a generated secret of at least 32 characters")
        return value

    @field_validator("zeek_shared_token")
    @classmethod
    def validate_zeek_shared_token(cls, value: str) -> str:
        if value and len(value) < 32:
            raise ValueError("ZEEK_SHARED_TOKEN must be empty or at least 32 characters")
        return value


def get_settings() -> Settings:
    return Settings()
