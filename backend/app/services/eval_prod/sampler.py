"""Read-only, seeded sampler over `llm_usage_events` (MLH-T18 slice 3, decision D11).

Reproducible: for the same tasks, window, limit and seed the same rows come back in the same
order, because rows are ranked by `md5(id || seed)` (id as the tie-break). Bounded: at most
`min(limit_per_task, HARD_MAX_PER_TASK)` rows per task, in ONE statement. Read-only: nothing
here adds, flushes, commits or deletes.

TENANCY (CONSTITUTION Rules 3 and 12). `llm_usage_events.school_id` is nullable (NULL =
platform-level work) and this sample deliberately spans every school, so there is no
`school_id` filter. That is only acceptable for a Kaihle Admin, and the bypass is explicit:
both public functions require the actor to be `KAIHLE_ADMIN` and raise otherwise.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, String, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsageEvent
from app.models.school import School
from app.models.user import User, UserRole

HARD_MAX_PER_TASK = 200


class SamplerAccessError(PermissionError):
    """The caller is not a Kaihle Admin; the cross-school read is refused."""


@dataclass(frozen=True)
class SampledEvent:
    """The columns an evaluation needs. `school_id` is carried as-is (None = platform-level)."""

    id: uuid.UUID
    task: str
    model: str
    component: str | None
    school_id: uuid.UUID | None
    prompt_text: str | None
    response_text: str
    created_at: datetime


@dataclass(frozen=True)
class ScrubNames:
    """Names to mask for one school: its users' display names and the school's own name."""

    person_names: tuple[str, ...]
    school_name: str | None


def _require_kaihle_admin(actor: User) -> None:
    if actor.role == UserRole.KAIHLE_ADMIN:
        return  # explicit bypass (Rule 12)
    raise SamplerAccessError("Cross-school sampling is restricted to Kaihle Admin")


def build_sample_statement(
    tasks: Collection[str], window_start: datetime, window_end: datetime, limit_per_task: int, seed: str
) -> Select[tuple[uuid.UUID, str, str, str | None, uuid.UUID | None, str | None, str, datetime]]:
    """SELECT-only statement: succeeded rows with a response, ranked per task by the seeded hash."""
    order_key = func.md5(func.concat(cast(LlmUsageEvent.id, String), literal(seed, String)))
    rank = func.row_number().over(partition_by=LlmUsageEvent.task, order_by=(order_key, LlmUsageEvent.id)).label("rn")
    ranked = (
        select(
            LlmUsageEvent.id,
            LlmUsageEvent.task,
            LlmUsageEvent.model,
            LlmUsageEvent.component,
            LlmUsageEvent.school_id,
            LlmUsageEvent.prompt_text,
            LlmUsageEvent.response_text,
            LlmUsageEvent.created_at,
            rank,
        )
        .where(
            LlmUsageEvent.task.in_(list(tasks)),
            LlmUsageEvent.succeeded.is_(True),
            LlmUsageEvent.response_text.is_not(None),
            LlmUsageEvent.created_at >= window_start,
            LlmUsageEvent.created_at < window_end,
        )
        .subquery("ranked")
    )
    return (
        select(
            ranked.c.id,
            ranked.c.task,
            ranked.c.model,
            ranked.c.component,
            ranked.c.school_id,
            ranked.c.prompt_text,
            ranked.c.response_text,
            ranked.c.created_at,
        )
        .where(ranked.c.rn <= limit_per_task)
        .order_by(ranked.c.task, ranked.c.rn)
    )


async def sample_usage_events(
    db: AsyncSession,
    *,
    actor: User,
    tasks: Sequence[str],
    window_start: datetime,
    window_end: datetime,
    limit_per_task: int,
    seed: str,
) -> list[SampledEvent]:
    """Seeded sample of usage events per task in [window_start, window_end). Read-only."""
    _require_kaihle_admin(actor)
    if limit_per_task < 1:
        raise ValueError("limit_per_task must be at least 1")
    if window_start >= window_end:
        raise ValueError("window_start must be before window_end")
    if not tasks:
        return []
    statement = build_sample_statement(tasks, window_start, window_end, min(limit_per_task, HARD_MAX_PER_TASK), seed)
    result = await db.execute(statement)
    return [
        SampledEvent(
            id=row.id,
            task=row.task,
            model=row.model,
            component=row.component,
            school_id=row.school_id,
            prompt_text=row.prompt_text,
            response_text=row.response_text,
            created_at=row.created_at,
        )
        for row in result
    ]


async def load_scrub_names(
    db: AsyncSession, actor: User, school_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, ScrubNames]:
    """Read-only: display names of every user, plus the name, of each requested school.

    Bounded by the requested school set. Inactive users are included on purpose — their
    names can still appear in historic text.
    """
    _require_kaihle_admin(actor)
    if not school_ids:
        return {}
    wanted = list(school_ids)
    names: dict[uuid.UUID, list[str]] = {sid: [] for sid in wanted}
    user_rows = await db.execute(
        select(User.school_id, User.first_name, User.last_name).where(User.school_id.in_(wanted))
    )
    for school_id, first_name, last_name in user_rows:
        names[school_id].append(f"{first_name} {last_name}".strip())
    school_rows = await db.execute(select(School.id, School.name).where(School.id.in_(wanted)))
    school_names = {sid: name for sid, name in school_rows}
    return {
        sid: ScrubNames(person_names=tuple(person_names), school_name=school_names.get(sid))
        for sid, person_names in names.items()
        if sid in school_names
    }
