"""Platform settings — the Kaihle Admin production-evaluation controls (MLH-T18).

Platform-wide singleton (see `PlatformSettings`), KAIHLE_ADMIN only; the route enforces the
role, this service owns every rule about the values.

DESIGN DECISIONS
  * Reading never writes: with no row, `get_eval_settings` returns the fail-closed defaults
    (budget 0, nothing enabled) without inserting.
  * Full replacement on update, idempotent: an identical payload changes nothing (no new
    `updated_at`/`updated_by`, no new acknowledgement timestamp, no log line).
  * Acknowledgements are append-only history. Disabling a task keeps its acknowledgement
    (the record of who accepted the privacy risk and when); re-enabling it does not demand a
    fresh one. The privacy gate is therefore "has this task EVER been acknowledged", and the
    first enablement always requires it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.router import TASK_MODEL_MAP
from app.models.platform_settings import PlatformSettings

logger = structlog.get_logger()

DEFAULT_SAMPLE_SIZE = 50
DEFAULT_WINDOW_DAYS = 7
MIN_SAMPLE_SIZE, MAX_SAMPLE_SIZE = 1, 200
MIN_WINDOW_DAYS, MAX_WINDOW_DAYS = 1, 90
# Numeric(12, 2) column.
MAX_BUDGET_USD = Decimal("9999999999.99")
_CENTS = Decimal("0.01")

# Router tasks that can never be sampled: the judge itself (evaluating it is circular and its
# calls are the spend being budgeted) and embeddings (no text response to evaluate).
NON_EVALUABLE_TASKS: frozenset[str] = frozenset({"eval_judge", "embeddings"})

# Tasks whose prompt or response carries student-derived text, so enabling them needs an
# explicit privacy acknowledgement (T18 D5). Verified against prompts and call sites
# 2026-10-11:
#   grade_open_answer        - the student's free-text answer is in the prompt.
#   explain_this, concept_guide - the student's own question is in the prompt (incl. MCQ feedback).
#   transfer_question, mini_course_explanation, lesson_plan - no student-authored free text,
#       but they embed student-derived profile data (interests, learning modality, class
#       aggregates). Flagged deliberately: for a platform serving minors, the acknowledgement
#       gate should err toward asking.
# Not flagged: question_generation, question_quality, content_seed, lo_matching,
# quiz_generation (curriculum-wide / batch work with no student input).
TASKS_WITH_STUDENT_TEXT: frozenset[str] = frozenset(
    {
        "grade_open_answer",
        "explain_this",
        "concept_guide",
        "transfer_question",
        "mini_course_explanation",
        "lesson_plan",
    }
)


class EvalSettingsValidationError(ValueError):
    """The submitted settings break a rule. Safe to show to the admin; routes map it to 422."""


@dataclass(frozen=True)
class EvalSettings:
    """Immutable snapshot of the evaluation settings (defaults when no row exists)."""

    monthly_budget_usd: Decimal
    enabled_tasks: list[str]
    sample_size_per_task: int
    window_days: int
    include_indicative: bool
    student_text_ack: dict[str, dict[str, str]]
    updated_by: UUID | None
    updated_at: datetime | None


def available_tasks() -> list[str]:
    """Router tasks an admin may put on the allowlist, sorted for a stable UI."""
    return sorted(set(TASK_MODEL_MAP) - NON_EVALUABLE_TASKS)


def _snapshot(row: PlatformSettings | None) -> EvalSettings:
    if row is None:
        return EvalSettings(
            monthly_budget_usd=Decimal("0"),
            enabled_tasks=[],
            sample_size_per_task=DEFAULT_SAMPLE_SIZE,
            window_days=DEFAULT_WINDOW_DAYS,
            include_indicative=False,
            student_text_ack={},
            updated_by=None,
            updated_at=None,
        )
    return EvalSettings(
        monthly_budget_usd=row.eval_monthly_budget_usd,
        enabled_tasks=list(row.eval_enabled_tasks),
        sample_size_per_task=row.eval_sample_size_per_task,
        window_days=row.eval_window_days,
        include_indicative=row.eval_include_indicative,
        student_text_ack={task: dict(ack) for task, ack in row.eval_student_text_ack.items()},
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


class PlatformSettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_eval_settings(self) -> EvalSettings:
        """Read the settings. Pure read: returns defaults when no row exists, never inserts."""
        result = await self._db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
        return _snapshot(result.scalar_one_or_none())

    async def update_eval_settings(
        self,
        *,
        actor_id: UUID,
        monthly_budget_usd: Decimal,
        enabled_tasks: list[str],
        sample_size_per_task: int,
        window_days: int,
        include_indicative: bool,
        acknowledge_student_text_tasks: list[str],
    ) -> EvalSettings:
        """Validate and persist the settings in one transaction (writes the row, commits).

        Raises EvalSettingsValidationError before touching the database when any rule is
        broken. Concurrent first-time saves are safe: the row is inserted with
        ON CONFLICT DO NOTHING, then locked with SELECT ... FOR UPDATE.
        """
        budget = self._validate_budget(monthly_budget_usd)
        tasks = self._validate_tasks(enabled_tasks)
        if not MIN_SAMPLE_SIZE <= sample_size_per_task <= MAX_SAMPLE_SIZE:
            raise EvalSettingsValidationError(
                f"sample size per task must be between {MIN_SAMPLE_SIZE} and {MAX_SAMPLE_SIZE}"
            )
        if not MIN_WINDOW_DAYS <= window_days <= MAX_WINDOW_DAYS:
            raise EvalSettingsValidationError(
                f"evaluation window must be between {MIN_WINDOW_DAYS} and {MAX_WINDOW_DAYS} days"
            )
        to_acknowledge = self._validate_acknowledgements(acknowledge_student_text_tasks, tasks)

        await self._db.execute(pg_insert(PlatformSettings).values(id=1).on_conflict_do_nothing())
        result = await self._db.execute(select(PlatformSettings).where(PlatformSettings.id == 1).with_for_update())
        row = result.scalar_one()

        ack = dict(row.eval_student_text_ack)
        new_acks = [task for task in to_acknowledge if task not in ack]
        missing = [
            task for task in tasks if task in TASKS_WITH_STUDENT_TEXT and task not in ack and task not in new_acks
        ]
        if missing:
            # Undo the lazily inserted row so a rejected first save leaves no trace.
            await self._db.rollback()
            raise EvalSettingsValidationError(
                f"task(s) {', '.join(sorted(missing))} contain student text; "
                "explicit acknowledgement is required before enabling"
            )

        unchanged = (
            row.eval_monthly_budget_usd == budget
            and list(row.eval_enabled_tasks) == tasks
            and row.eval_sample_size_per_task == sample_size_per_task
            and row.eval_window_days == window_days
            and row.eval_include_indicative == include_indicative
            and not new_acks
        )
        if unchanged:
            await self._db.commit()
            return _snapshot(row)

        previous_budget = row.eval_monthly_budget_usd
        previous_tasks = list(row.eval_enabled_tasks)
        now = datetime.now(UTC)
        for task in new_acks:
            ack[task] = {"acknowledged_by": str(actor_id), "acknowledged_at": now.isoformat()}

        row.eval_monthly_budget_usd = budget
        row.eval_enabled_tasks = tasks
        row.eval_sample_size_per_task = sample_size_per_task
        row.eval_window_days = window_days
        row.eval_include_indicative = include_indicative
        row.eval_student_text_ack = ack  # reassigned, not mutated in place, so JSONB change is detected
        row.updated_by = actor_id
        row.updated_at = now
        snapshot = _snapshot(row)
        await self._db.commit()

        logger.info(
            "platform_settings.eval_updated",
            actor_id=str(actor_id),
            previous_budget_usd=str(previous_budget),
            new_budget_usd=str(budget),
            tasks_added=[task for task in tasks if task not in previous_tasks],
            tasks_removed=[task for task in previous_tasks if task not in tasks],
            newly_acknowledged_tasks=new_acks,
            sample_size_per_task=sample_size_per_task,
            window_days=window_days,
            include_indicative=include_indicative,
        )
        return snapshot

    @staticmethod
    def _validate_budget(value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > MAX_BUDGET_USD:
            raise EvalSettingsValidationError(f"monthly budget must be a number between 0 and {MAX_BUDGET_USD}")
        return value.quantize(_CENTS)

    @staticmethod
    def _validate_tasks(enabled_tasks: list[str]) -> list[str]:
        tasks = list(dict.fromkeys(enabled_tasks))  # de-duplicate, keep order
        allowed = set(available_tasks())
        for task in tasks:
            if task not in allowed:
                raise EvalSettingsValidationError(f"task {task!r} is not an evaluable router task")
        return tasks

    @staticmethod
    def _validate_acknowledgements(requested: list[str], enabled_tasks: list[str]) -> list[str]:
        acknowledged: list[str] = []
        for task in dict.fromkeys(requested):
            if task not in TASKS_WITH_STUDENT_TEXT:
                raise EvalSettingsValidationError(
                    f"task {task!r} does not contain student text; nothing to acknowledge"
                )
            if task not in enabled_tasks:
                raise EvalSettingsValidationError(f"task {task!r} is not being enabled; acknowledge it when enabling")
            acknowledged.append(task)
        return acknowledged
