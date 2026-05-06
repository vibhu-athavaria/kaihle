import json

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    resend_api_key: str = ""
    from_email: str = "no-reply@kaihle.ai"
    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    youtube_data_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "kaihle-assets"
    aws_region: str = "ap-southeast-1"
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    environment: str = "development"
    log_level: str = "INFO"

    # LLM task routing — all overridable via environment variables
    llm_gap_classification_model: str = "gemini/gemini-2.5-flash"
    llm_gap_classification_api_base: str | None = None

    llm_study_plan_model: str = "gpt-4.1-mini"
    llm_study_plan_api_base: str | None = None

    llm_lesson_plan_model: str = "gpt-4.1"
    llm_lesson_plan_api_base: str | None = None

    llm_embeddings_model: str = "text-embedding-004"
    llm_embeddings_api_base: str | None = None

    llm_question_generation_model: str = "gemini/gemini-2.5-flash"
    llm_question_generation_api_base: str | None = None

    llm_student_pack_model: str = "gemini/gemini-2.5-pro"
    llm_student_pack_api_base: str | None = None

    llm_concept_guide_model: str = "gemini/gemini-2.5-flash"
    llm_concept_guide_api_base: str | None = None

    # Platform stats — overridable via environment variables
    platform_llm_provider: str = "openai"
    platform_runpod_status: str = "blocked"
    platform_trial_days: int = 14
    platform_trial_students_limit: int = 30
    platform_rate_limit_requests_per_minute: int = 100
    platform_rate_limit_concurrent_users: int = 50

    # Per-role frontend app URLs — used to build login/reset links in emails
    teacher_app_url: str = "http://localhost:3001"
    student_app_url: str = "http://localhost:3002"
    parent_app_url: str = "http://localhost:3003"
    school_admin_app_url: str = "http://localhost:3004"
    kaihle_admin_app_url: str = "http://localhost:3005"

    @model_validator(mode="after")
    def _validate_production_app_urls(self) -> "Settings":
        """Fail fast at startup if any app URL still points to localhost in production."""
        if self.environment == "production":
            localhost_urls = [
                name
                for name, url in {
                    "TEACHER_APP_URL": self.teacher_app_url,
                    "STUDENT_APP_URL": self.student_app_url,
                    "PARENT_APP_URL": self.parent_app_url,
                    "SCHOOL_ADMIN_APP_URL": self.school_admin_app_url,
                    "KAIHLE_ADMIN_APP_URL": self.kaihle_admin_app_url,
                }.items()
                if "localhost" in url
            ]
            if localhost_urls:
                raise ValueError(
                    f"Production deployment has localhost app URLs — emails will contain broken links. "
                    f"Set these env vars to their public URLs: {', '.join(localhost_urls)}"
                )
        return self

    # CORS — stored as raw string, parsed at runtime via property
    # Set CORS_ORIGINS_RAW in Render as comma-separated:
    # https://teacher.kaihle.com,https://admin.kaihle.com,...
    cors_origins_raw: str = (
        "http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:3004,http://localhost:3005"
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string or JSON array."""
        v = self.cors_origins_raw.strip()
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]


settings = Settings()
