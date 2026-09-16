from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    luma_api_key: str
    public_base_url: str = "http://127.0.0.1:8000"
    luma_endpoint: str = "https://agents.lumalabs.ai/v1/generations"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
