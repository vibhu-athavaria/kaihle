"""Integration tests for the production-evaluation sampler (MLH-T18 slice 3). Real Postgres."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsageEvent
from app.models.school import School
from app.models.user import User
from app.services.eval_prod import sampler
from app.services.eval_prod.sampler import (
    HARD_MAX_PER_TASK,
    SamplerAccessError,
    build_sample_statement,
    load_scrub_names,
    sample_usage_events,
)

NOW = datetime.now(UTC)
WINDOW_START = NOW - timedelta(days=7)
WINDOW_END = NOW + timedelta(minutes=1)
TASK = "question_generation"


async def _seed(db: AsyncSession, count: int, **overrides: Any) -> list[uuid.UUID]:
    ids = []
    for _ in range(count):
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "task": TASK,
            "model": "test/model-a",
            "latency_ms": 5,
            "created_at": NOW - timedelta(hours=1),
            "succeeded": True,
            "prompt_text": "prompt",
            "response_text": "response",
        }
        values.update(overrides)
        db.add(LlmUsageEvent(**values))
        ids.append(values["id"])
    await db.commit()
    return ids


async def _sample(db: AsyncSession, actor: User, **overrides: Any) -> list[Any]:
    kwargs: dict[str, Any] = {
        "actor": actor,
        "tasks": [TASK],
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "limit_per_task": 50,
        "seed": "s1",
    }
    kwargs.update(overrides)
    return await sample_usage_events(db, **kwargs)


async def test_sample_when_seed_same_then_same_rows_in_same_order(db_session: AsyncSession, kaihle_admin: User) -> None:
    await _seed(db_session, 12)
    first = await _sample(db_session, kaihle_admin, limit_per_task=5)
    second = await _sample(db_session, kaihle_admin, limit_per_task=5)
    assert [e.id for e in first] == [e.id for e in second]
    assert len(first) == 5


async def test_sample_when_seed_differs_then_order_differs(db_session: AsyncSession, kaihle_admin: User) -> None:
    await _seed(db_session, 30)
    a = await _sample(db_session, kaihle_admin, seed="alpha")
    b = await _sample(db_session, kaihle_admin, seed="beta")
    assert [e.id for e in a] != [e.id for e in b]
    assert {e.id for e in a} == {e.id for e in b}


async def test_sample_when_limit_below_available_then_returns_exactly_limit(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _seed(db_session, 8)
    assert len(await _sample(db_session, kaihle_admin, limit_per_task=3)) == 3


async def test_sample_when_limit_exceeds_hard_max_then_clamped_to_hard_max(
    db_session: AsyncSession, kaihle_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session, 8)
    monkeypatch.setattr(sampler, "HARD_MAX_PER_TASK", 4)  # small cap so 8 seeded rows can show the clamp
    assert len(await _sample(db_session, kaihle_admin, limit_per_task=1000)) == 4


def test_hard_max_per_task_when_imported_then_is_200() -> None:
    assert HARD_MAX_PER_TASK == 200


async def test_sample_when_limit_applies_then_it_is_per_task(db_session: AsyncSession, kaihle_admin: User) -> None:
    await _seed(db_session, 4)
    await _seed(db_session, 4, task="content_seed")
    rows = await _sample(db_session, kaihle_admin, tasks=[TASK, "content_seed"], limit_per_task=2)
    assert sorted(e.task for e in rows) == ["content_seed", "content_seed", TASK, TASK]


async def test_sample_when_window_given_then_excludes_older_rows(db_session: AsyncSession, kaihle_admin: User) -> None:
    old = await _seed(db_session, 2, created_at=NOW - timedelta(days=30))
    recent = await _seed(db_session, 2)
    ids = {e.id for e in await _sample(db_session, kaihle_admin)}
    assert ids == set(recent)
    assert not ids & set(old)


async def test_sample_when_row_failed_or_response_null_then_excluded(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _seed(db_session, 1, succeeded=False, error_type="Boom")
    await _seed(db_session, 1, response_text=None)
    keep = await _seed(db_session, 1)
    assert [e.id for e in await _sample(db_session, kaihle_admin)] == keep


async def test_sample_when_task_not_requested_then_excluded(db_session: AsyncSession, kaihle_admin: User) -> None:
    await _seed(db_session, 2, task="lesson_plan")
    assert await _sample(db_session, kaihle_admin) == []


async def test_sample_when_called_then_only_selects_and_never_writes(
    db_session: AsyncSession, kaihle_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session, 3)
    flush, commit = AsyncMock(), AsyncMock()
    monkeypatch.setattr(db_session, "flush", flush)
    monkeypatch.setattr(db_session, "commit", commit)
    await _sample(db_session, kaihle_admin)
    flush.assert_not_called()
    commit.assert_not_called()
    assert not db_session.new and not db_session.dirty and not db_session.deleted
    stmt = str(build_sample_statement([TASK], WINDOW_START, WINDOW_END, 5, "s1")).lstrip().upper()
    assert stmt.startswith("SELECT")
    assert all(word not in stmt for word in ("INSERT ", "UPDATE ", "DELETE "))


async def test_sample_when_empty_then_returns_empty_list(db_session: AsyncSession, kaihle_admin: User) -> None:
    assert await _sample(db_session, kaihle_admin) == []
    assert await _sample(db_session, kaihle_admin, tasks=[]) == []


async def test_sample_when_actor_not_kaihle_admin_then_access_denied(db_session: AsyncSession, teacher: User) -> None:
    with pytest.raises(SamplerAccessError):
        await _sample(db_session, teacher)


async def test_sample_when_arguments_invalid_then_raises_value_error(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    with pytest.raises(ValueError):
        await _sample(db_session, kaihle_admin, limit_per_task=0)
    with pytest.raises(ValueError):
        await _sample(db_session, kaihle_admin, window_start=WINDOW_END, window_end=WINDOW_START)


async def test_sample_when_event_has_school_then_school_id_carried_and_null_kept_null(
    db_session: AsyncSession, kaihle_admin: User, school: School
) -> None:
    with_school = await _seed(db_session, 1, school_id=school.id)
    without = await _seed(db_session, 1)
    by_id = {e.id: e for e in await _sample(db_session, kaihle_admin)}
    assert by_id[with_school[0]].school_id == school.id
    assert by_id[without[0]].school_id is None


async def test_load_scrub_names_when_school_given_then_returns_users_and_school_name(
    db_session: AsyncSession, kaihle_admin: User, school: School, student: User, other_school: School
) -> None:
    ctx = await load_scrub_names(db_session, kaihle_admin, {school.id})
    names = ctx[school.id]
    assert school.name == names.school_name
    assert f"{student.first_name} {student.last_name}" in names.person_names
    assert other_school.id not in ctx


async def test_load_scrub_names_when_actor_not_kaihle_admin_then_access_denied(
    db_session: AsyncSession, teacher: User, school: School
) -> None:
    with pytest.raises(SamplerAccessError):
        await load_scrub_names(db_session, teacher, {school.id})


async def test_load_scrub_names_when_no_school_ids_then_empty(db_session: AsyncSession, kaihle_admin: User) -> None:
    assert await load_scrub_names(db_session, kaihle_admin, set()) == {}
