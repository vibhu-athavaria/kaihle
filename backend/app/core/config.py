from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/school_management"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Kaihle Backend"

    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    # LLM-related fields
    LLM_PROVIDER: str = "gemini"  # "openai", "gemini", "ollama", "mock"
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OLLAMA_URL: str | None = None
    MOONSHOT_API_KEY: str | None = None
    MOONSHOT_API_URL: str | None = None
    # Assessment settings
    MAX_QUESTIONS_PER_ASSESSMENT: int = 32

    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_your_stripe_secret_key"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_your_stripe_publishable_key"


    class Config:
        env_file = ".env"

settings = Settings()

