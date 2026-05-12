from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg2://pind:pind_local@localhost:5433/pind"
    test_database_url: str = "postgresql+psycopg2://pind:pind_local@localhost:5434/pind_test"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_webhook_secret: str = ""

    # AI
    gemini_api_key: str = ""
    google_places_api_key: str = ""

    # Cost caps
    max_video_duration_sec: int = 1800  # 30 min
    max_frames_per_video: int = 60
    max_cost_per_video_usd: float = 0.50

    # App
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
