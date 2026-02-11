from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # ======================
    # Database (REQUIRED)
    # ======================
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")

    # ======================
    # Security
    # ======================
    SECRET_KEY: str = Field(..., description="JWT secret key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ======================
    # API
    # ======================
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Kaihle Backend"

    # ======================
    # CORS
    # ======================
    BACKEND_CORS_ORIGINS: List[str] = []

    # ======================
    # LLM
    # ======================
    LLM_PROVIDER: str = "gemini"
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OLLAMA_URL: str | None = None
    MOONSHOT_API_KEY: str | None = None
    MOONSHOT_API_URL: str | None = None

    # ======================
    # Assessment
    # ======================
    MAX_QUESTIONS_PER_ASSESSMENT: int = 32

    # ======================
    # Stripe
    # ======================
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
