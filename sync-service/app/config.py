from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    sync_interval_minutes: int = 5
    gemini_api_key: str
    actual_bridge_url: str = "http://actual-bridge:3000"
    telegram_bot_token: str
    telegram_chat_id: str

    class Config:
        env_file = ".env"


settings = Settings()
