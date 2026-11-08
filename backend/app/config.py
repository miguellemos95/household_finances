from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://household:household_dev@localhost:5432/household_finances"
    )
    frontend_origin: str = "http://localhost:4200"
