"""Platform-level endpoints for Kaihle Admin operations."""

import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.auth import ImpersonationStartResponse
from app.schemas.eval_settings import (
    EvalSettingsResponse,
    EvalSettingsUpdateRequest,
    StudentTextAcknowledgement,
)
from app.schemas.llm_logs import (
    LlmLogDetailResponse,
    LlmLogFilterOptionsResponse,
    LlmLogsResponse,
    LlmLogSummaryResponse,
)
from app.schemas.quality import (
    QualityBucket,
    QualityBudgetResponse,
    QualityFailuresResponse,
    QualitySummaryResponse,
)
from app.services.auth_service import (
    AuthService,
    ImpersonationNotAllowedError,
    UserNotFoundError,
)
from app.services.llm_log_service import (
    DEFAULT_LOG_PAGE_SIZE,
    InvalidSortError,
    LlmLogSummary,
    get_llm_log,
    list_llm_log_filter_options,
    list_llm_logs,
)
from app.services.platform_settings_service import (
    TASKS_WITH_STUDENT_TEXT,
    EvalSettings,
    EvalSettingsValidationError,
    PlatformSettingsService,
    available_tasks,
)
from app.services.quality_summary_service import (
    DEFAULT_FAILURES_PAGE_SIZE,
    MAX_FAILURES_PAGE_SIZE,
    QualityQueryError,
    QualitySummaryService,
    resolve_window,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/platform", tags=["platform"])
logger = structlog.get_logger()


class PlatformStatsResponse(BaseModel):
    """Platform configuration and statistics."""

    llm_provider: str
    runpod_status: str
    trial_days: int
    trial_students_limit: int
    rate_limit_requests_per_minute: int
    rate_limit_concurrent_users: int


class PlatformUserSummary(BaseModel):
    """Summary of a platform user."""

    id: str
    school_id: str | None
    first_name: str
    last_name: str
    email: str
    username: str | None = None
    role: str
    is_active: bool
    last_active: str | None
    school_name: str | None = None


class PlatformUsersResponse(BaseModel):
    """Paginated list of platform users."""

    users: list[PlatformUserSummary]
    total: int
    page: int
    page_size: int


@router.get("/stats")
async def get_platform_stats(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> PlatformStatsResponse:
    """Get platform configuration and statistics.

    Returns platform-wide configuration values including LLM provider settings,
    trial settings, and rate limits.
    """
    logger.info("platform.stats.requested", user_id=str(current_user.id))
    return PlatformStatsResponse(
        llm_provider=settings.platform_llm_provider,
        runpod_status=settings.platform_runpod_status,
        trial_days=settings.platform_trial_days,
        trial_students_limit=settings.platform_trial_students_limit,
        rate_limit_requests_per_minute=settings.platform_rate_limit_requests_per_minute,
        rate_limit_concurrent_users=settings.platform_rate_limit_concurrent_users,
    )


@router.post("/users/{user_id}/impersonate", response_model=ImpersonationStartResponse)
async def impersonate_user(
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ImpersonationStartResponse:
    """Mint a single-use link that opens a session as the given user.

    KAIHLE_ADMIN only. The link points at the app that serves the target's role
    and is redeemed by POST /api/v1/auth/impersonate/redeem.
    Returns 404 if the user does not exist, 403 if they may not be impersonated.
    """
    service = AuthService(db)
    try:
        return await service.start_impersonation(current_user, user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ImpersonationNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/users")
async def get_platform_users(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    q: str | None = Query(None, description="Search query (name or email)"),
    role: str | None = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> PlatformUsersResponse:
    """Get paginated list of platform users.

    Returns a list of all users across all schools with optional filtering.
    KAIHLE_ADMIN bypass - no school_id filter applied (Rule 12 explicit).
    """
    logger.info(
        "platform.users.requested",
        user_id=str(current_user.id),
        q=q,
        role=role,
        page=page,
        page_size=page_size,
    )

    service = UserService(db)
    users, total = await service.list_platform_users(q, role, page, page_size)

    return PlatformUsersResponse(
        users=[
            PlatformUserSummary(
                id=str(row.user.id),
                school_id=str(row.user.school_id) if row.user.school_id else None,
                first_name=row.user.first_name or "",
                last_name=row.user.last_name or "",
                email=row.user.email or "",
                username=row.user.username or "",
                role=row.user.role,
                is_active=row.user.is_active,
                last_active=row.user.last_login_at.isoformat() if row.user.last_login_at else None,
                school_name=row.school_name,
            )
            for row in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _log_summary_response(log: LlmLogSummary) -> LlmLogSummaryResponse:
    """`LlmLogDetail` is also a `LlmLogSummary` (it subclasses it), so this covers both
    the list route and the shared base fields of the detail route below."""
    return LlmLogSummaryResponse(
        id=str(log.id),
        created_at=log.created_at,
        task=log.task,
        model=log.model,
        component=log.component,
        run_id=log.run_id,
        prompt_tokens=log.prompt_tokens,
        completion_tokens=log.completion_tokens,
        total_tokens=log.total_tokens,
        latency_ms=log.latency_ms,
        estimated_cost_usd=float(log.estimated_cost_usd) if log.estimated_cost_usd is not None else None,
        succeeded=log.succeeded,
        error_type=log.error_type,
    )


@router.get("/llm-logs")
async def get_llm_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_LOG_PAGE_SIZE, ge=1, le=200),
    task: str | None = Query(None, description="Exact task filter, e.g. 'question_generation'"),
    model: str | None = Query(None, description="Exact model filter"),
    sort_by: Literal["created_at", "task", "model", "latency_ms", "cost", "tokens"] = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LlmLogsResponse:
    """Paginated list of individual LLM calls — filterable by exact task/model, sortable
    by any of the columns above, most-recent-first by default. Click a row in the admin UI
    to fetch its full detail (prompt/response text) via GET /llm-logs/{id}.
    """
    logger.info(
        "platform.llm_logs.requested",
        user_id=str(current_user.id),
        page=page,
        page_size=page_size,
        task=task,
        model=model,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    try:
        logs, total = await list_llm_logs(
            db, page=page, page_size=page_size, task=task, model=model, sort_by=sort_by, sort_dir=sort_dir
        )
    except InvalidSortError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    return LlmLogsResponse(
        logs=[_log_summary_response(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/llm-logs/filter-options")
async def get_llm_log_filter_options(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LlmLogFilterOptionsResponse:
    """Distinct task/model values that actually have logged calls, for the filter
    dropdowns. Registered before /llm-logs/{log_id} — a static path must precede a
    dynamic one, or FastAPI (correctly) tries to parse "filter-options" as a UUID.
    """
    logger.info("platform.llm_log_filter_options.requested", user_id=str(current_user.id))

    tasks, models = await list_llm_log_filter_options(db)
    return LlmLogFilterOptionsResponse(tasks=tasks, models=models)


@router.get("/llm-logs/{log_id}")
async def get_llm_log_detail(
    log_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LlmLogDetailResponse:
    """Full detail for one LLM call, including prompt/response text. 404 if the id
    doesn't exist."""
    logger.info("platform.llm_log_detail.requested", user_id=str(current_user.id), log_id=str(log_id))

    log = await get_llm_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM log not found")

    return LlmLogDetailResponse(
        **_log_summary_response(log).model_dump(),
        prompt_text=log.prompt_text,
        response_text=log.response_text,
        error_detail=log.error_detail,
        correlation_id=log.correlation_id,
        school_id=str(log.school_id) if log.school_id else None,
        streamed=log.streamed,
    )


def _eval_settings_response(eval_settings: EvalSettings) -> EvalSettingsResponse:
    return EvalSettingsResponse(
        eval_monthly_budget_usd=float(eval_settings.monthly_budget_usd),
        eval_enabled_tasks=eval_settings.enabled_tasks,
        eval_sample_size_per_task=eval_settings.sample_size_per_task,
        eval_window_days=eval_settings.window_days,
        eval_include_indicative=eval_settings.include_indicative,
        student_text_acknowledgements={
            task: StudentTextAcknowledgement(**ack) for task, ack in eval_settings.student_text_ack.items()
        },
        available_tasks=available_tasks(),
        tasks_with_student_text=sorted(TASKS_WITH_STUDENT_TEXT),
        updated_by=str(eval_settings.updated_by) if eval_settings.updated_by else None,
        updated_at=eval_settings.updated_at,
    )


@router.get("/eval-settings")
async def get_eval_settings(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EvalSettingsResponse:
    """Production-evaluation settings. Fail-closed defaults (budget 0, nothing enabled) when
    nothing has been saved yet. KAIHLE_ADMIN only (Rule 12: no school_id filter applies to
    platform-wide settings)."""
    logger.info("platform.eval_settings.requested", user_id=str(current_user.id))
    return _eval_settings_response(await PlatformSettingsService(db).get_eval_settings())


@router.put("/eval-settings")
async def update_eval_settings(
    body: EvalSettingsUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EvalSettingsResponse:
    """Replace the production-evaluation settings. 422 on any rule violation (negative
    budget, out-of-range sample/window, unknown task, student-text task without
    acknowledgement). Idempotent for an identical payload. KAIHLE_ADMIN only."""
    try:
        eval_settings = await PlatformSettingsService(db).update_eval_settings(
            actor_id=current_user.id,
            monthly_budget_usd=body.eval_monthly_budget_usd,
            enabled_tasks=body.eval_enabled_tasks,
            sample_size_per_task=body.eval_sample_size_per_task,
            window_days=body.eval_window_days,
            include_indicative=body.eval_include_indicative,
            acknowledge_student_text_tasks=body.acknowledge_student_text_tasks,
        )
    except EvalSettingsValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    return _eval_settings_response(eval_settings)


@router.get("/quality/summary")
async def get_quality_summary(
    window_start: datetime | None = Query(None, description="Inclusive start (tz-aware). Default: 28 days before end"),
    window_end: datetime | None = Query(None, description="Exclusive end (tz-aware). Default: now"),
    task: str | None = Query(None, description="Exact task filter"),
    bucket: QualityBucket = Query("week", description="'week' = UTC ISO-week buckets, 'none' = whole window"),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QualitySummaryResponse:
    """Production-evaluation pass rates per task and check, with n and Wilson interval.
    Indeterminate results are reported separately and excluded from n. Each row carries its
    rubric status (INDICATIVE rows are flagged). Empty list when nothing has been evaluated.
    Read-only, ids and numbers only. KAIHLE_ADMIN only (Rule 12: platform-wide)."""
    logger.info("platform.quality_summary.requested", user_id=str(current_user.id), task=task, bucket=bucket)
    start, end = resolve_window(window_start, window_end, datetime.now(UTC))
    try:
        return await QualitySummaryService(db).summary(window_start=start, window_end=end, task=task, bucket=bucket)
    except QualityQueryError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.get("/quality/failures")
async def get_quality_failures(
    window_start: datetime | None = Query(None),
    window_end: datetime | None = Query(None),
    task: str | None = Query(None),
    check_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_FAILURES_PAGE_SIZE, ge=1, le=MAX_FAILURES_PAGE_SIZE),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QualityFailuresResponse:
    """Failed checks, newest first: usage_event_id + check name (+ task, time) only, never any
    text. Open the entry via GET /llm-logs/{usage_event_id}. KAIHLE_ADMIN only."""
    logger.info("platform.quality_failures.requested", user_id=str(current_user.id), task=task, page=page)
    start, end = resolve_window(window_start, window_end, datetime.now(UTC))
    try:
        return await QualitySummaryService(db).failures(
            window_start=start, window_end=end, task=task, check_name=check_name, page=page, page_size=page_size
        )
    except QualityQueryError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.get("/quality/budget")
async def get_quality_budget(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QualityBudgetResponse:
    """Monthly evaluation budget, month-to-date spend (UTC month, unpriced calls at worst case)
    and remaining budget. KAIHLE_ADMIN only."""
    logger.info("platform.quality_budget.requested", user_id=str(current_user.id))
    return await QualitySummaryService(db).budget_status(settings, datetime.now(UTC))
