from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    PROJECT_NAME: str = "FUSION 2026 - Geospatial Intelligence Query Understanding"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database Settings (PostgreSQL / Supabase / PostGIS)
    DATABASE_URL: Optional[str] = None
    SUPABASE_URL: Optional[str] = "https://ageskiwfgxjomotrfoqo.supabase.co"
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None

    # Groq LLM Settings
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Data Retrieval Engine API Keys & Tokens
    NASA_FIRMS_KEY: str = ""
    OPENTOPOGRAPHY_API_KEY: str = ""
    NASA_EARTHDATA_TOKEN: str = ""
    USGS_EARTHEXPLORER_TOKEN: str = ""

    @model_validator(mode="after")
    def populate_defaults(self):
        if not self.SUPABASE_ANON_KEY and self.SUPABASE_PUBLISHABLE_KEY:
            self.SUPABASE_ANON_KEY = self.SUPABASE_PUBLISHABLE_KEY
        if not self.DATABASE_URL:
            self.DATABASE_URL = "postgresql://postgres.ageskiwfgxjomotrfoqo:y5Q%21Rz8._Gbwfv6@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
