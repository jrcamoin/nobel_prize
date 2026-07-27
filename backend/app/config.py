from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Open Antibiotic Discovery API"
    database_url: str = "sqlite:///./nobel_prize.db"
    api_cors_origins: str = "http://localhost:5173"
    api_write_key: str = ""
    preregistration_signing_key: str = ""
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "antibiotic-artifacts"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
