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
    # Redis
    # ======================
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ======================
    # LLM
    # ======================
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 4000
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT_SECONDS: int = 90
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GOOGLE_MODEL: str = "gemini-1.5-flash"
    RUNPOD_API_BASE: str | None = None
    RUNPOD_API_KEY: str | None = None
    RUNPOD_MODEL: str | None = None
    AUTOCONTENTAPI_BASE_URL: str | None = None
    AUTOCONTENTAPI_KEY: str | None = None
    AUTOCONTENTAPI_MODEL: str | None = None
    OLLAMA_URL: str | None = None
    MOONSHOT_API_KEY: str | None = None
    MOONSHOT_API_URL: str | None = None

    # ======================
    # Assessment
    # ======================
    MAX_QUESTIONS_PER_ASSESSMENT: int = 32

    # ======================
    # Diagnostic Assessment
    # ======================
    DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC: int = 5
    DIAGNOSTIC_STARTING_DIFFICULTY: int = 3

    # ======================
    # Stripe
    # ======================
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
