"""Application settings, loaded from the environment (or a local .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://excel:excel@localhost:5432/excel"
    test_database_url: str = "postgresql+psycopg://excel:excel@localhost:5432/excel_test"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    session_hours: int = 8

    admin_email: str = "admin@excelengineers.in"
    admin_password: str = "change-me-admin"
    admin_full_name: str = "Admin"

    cors_origins: str = ""
    app_version: str = "0.1.0"

    # "production", "development" or "test". Defaults to production so a
    # server that sets nothing gets the strict behaviour (Secure cookie, HSTS,
    # no API docs, secret checks); only a machine that says otherwise is lax.
    environment: str = "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        """Anything but an explicit development or test environment is production."""
        return self.environment.strip().lower() not in {"development", "dev", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
