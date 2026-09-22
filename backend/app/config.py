from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    luma_api_key: str
    public_base_url: str = "http://127.0.0.1:8000"
    # Optional shared-secret for POST /api/generations and /api/assets. Unset
    # (the default) means those endpoints are unauthenticated, matching
    # today's deployment; set it to require an X-API-Key header. See
    # app/security.py for why this exists and how to turn it on.
    app_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
