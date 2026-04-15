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


settings = Settings()
