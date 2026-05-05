from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str

    # OpenRouter
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-4o-mini"

    # App
    app_env: str = "development"
    secret_key: str = "dev_secret"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
