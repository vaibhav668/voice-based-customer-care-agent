from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    app_version: str
    app_env: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    debug: bool
    llm_provider: str

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-20b:free"

    host: str
    port: int

    api_prefix: str
    database_url: str

    log_level: str = "INFO"
    allowed_origins: str = "*"

    telephony_provider: str = "plivo"
    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_phone_number: str = ""
    plivo_validate_signature: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()