"""The sampler accepts a role-carrying actor; the Rule 12 guard stays strict (MLH-T18 slice 5b-i)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from app.services.eval_prod.sampler import (
    SYSTEM_EVAL_ACTOR,
    SamplerAccessError,
    SystemActor,
    load_scrub_names,
    sample_usage_events,
)

NOW = datetime.now(UTC)


def test_system_eval_actor_when_inspected_then_is_kaihle_admin() -> None:
    assert SYSTEM_EVAL_ACTOR.role == UserRole.KAIHLE_ADMIN


@pytest.mark.parametrize("role", [UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT])
async def test_sampler_when_actor_has_non_admin_role_then_access_error(role: UserRole) -> None:
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(SamplerAccessError):
        await sample_usage_events(
            db,
            actor=SystemActor(role=role),
            tasks=["t"],
            window_start=NOW - timedelta(days=1),
            window_end=NOW,
            limit_per_task=1,
            seed="s",
        )
    with pytest.raises(SamplerAccessError):
        await load_scrub_names(db, SystemActor(role=role), [uuid.uuid4()])
    db.execute.assert_not_called()


async def test_sampler_when_system_actor_and_no_tasks_then_allowed_and_empty() -> None:
    db = AsyncMock(spec=AsyncSession)
    rows = await sample_usage_events(
        db,
        actor=SYSTEM_EVAL_ACTOR,
        tasks=[],
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
        limit_per_task=1,
        seed="s",
    )
    assert rows == []
