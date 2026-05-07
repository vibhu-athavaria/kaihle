"""Unit tests for lesson_plan_service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.lesson_plan_service import (
    _to_response,
    edit_lesson_plan,
    generate_lesson_plan,
    get_lesson_plan,
    list_class_lesson_plans,
    update_lesson_plan_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_class(class_id=None, teacher_id=None, school_id=None):
    c = MagicMock()
    c.id = class_id or uuid.uuid4()
    c.teacher_id = teacher_id or uuid.uuid4()
    c.school_id = school_id or uuid.uuid4()
    return c


def _make_plan(plan_id=None, class_id=None, teacher_id=None, status="GENERATED"):
    p = MagicMock()
    p.id = plan_id or uuid.uuid4()
    p.class_id = class_id or uuid.uuid4()
    p.teacher_id = teacher_id or uuid.uuid4()
    p.week_start = None
    p.status = status
    p.focus_subtopic_ids = []
    p.gap_summary = {}
    p.generated_plan = {"starter_10min": "intro"}
    p.teacher_edits = None
    p.generated_at = datetime.now(UTC)
    p.failure_code = None
    p.failure_reason = None
    return p


def _scalar(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _scalars(values):
    r = MagicMock()
    inner = MagicMock()
    inner.all.return_value = values
    r.scalars.return_value = inner
    return r


# ---------------------------------------------------------------------------
# generate_lesson_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_lesson_plan_when_teacher_owns_class_then_dispatches_task():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()

    class_ = _make_class(class_id=class_id, teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_id, teacher_id=teacher_id, status="GENERATING")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(class_),  # _require_teacher_class
            _scalars([]),  # _build_gap_summary — GapState rows
            _scalars([]),  # _build_gap_summary — subtopics
        ]
    )
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()

    with patch("app.services.lesson_plan_service.LessonPlan", return_value=plan):
        with patch(
            "app.tasks.lesson_plan_tasks.generate_lesson_plan_task",
            mock_task,
        ):
            with patch(
                "app.services.lesson_plan_service.generate_lesson_plan.__module__",
                "app.services.lesson_plan_service",
            ):
                result = await generate_lesson_plan(
                    class_id=class_id,
                    teacher_id=teacher_id,
                    school_id=school_id,
                    focus_subtopic_ids=[subtopic_id],
                    duration_minutes=45,
                    db=mock_db,
                )

    assert result.class_id == class_id


@pytest.mark.asyncio
async def test_generate_lesson_plan_when_class_not_found_then_raises_404():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar(None))

    with pytest.raises(HTTPException) as exc_info:
        await generate_lesson_plan(
            class_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            focus_subtopic_ids=[uuid.uuid4()],
            duration_minutes=45,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_generate_lesson_plan_when_wrong_teacher_then_raises_403():
    school_id = uuid.uuid4()
    class_ = _make_class(school_id=school_id, teacher_id=uuid.uuid4())

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar(class_))

    with pytest.raises(HTTPException) as exc_info:
        await generate_lesson_plan(
            class_id=class_.id,
            teacher_id=uuid.uuid4(),  # different teacher
            school_id=school_id,
            focus_subtopic_ids=[uuid.uuid4()],
            duration_minutes=45,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# list_class_lesson_plans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_class_lesson_plans_when_valid_teacher_then_returns_page():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(class_),  # _require_teacher_class
            _scalar_one(1),  # count
            _scalars([plan]),  # list
        ]
    )

    page = await list_class_lesson_plans(
        class_id=class_.id,
        teacher_id=teacher_id,
        school_id=school_id,
        page=1,
        page_size=10,
        db=mock_db,
    )

    assert page.total == 1
    assert len(page.data) == 1


# ---------------------------------------------------------------------------
# get_lesson_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_lesson_plan_when_plan_exists_then_merges_edits():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id)
    plan.teacher_edits = {"starter_10min": "edited starter"}

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),  # plan fetch
            _scalar(class_),  # class school check
        ]
    )

    response = await get_lesson_plan(
        plan_id=plan.id,
        teacher_id=teacher_id,
        school_id=school_id,
        db=mock_db,
    )

    assert response.generated_plan is not None
    assert response.generated_plan.get("starter_10min") == "edited starter"


@pytest.mark.asyncio
async def test_get_lesson_plan_when_plan_not_found_then_raises_404():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar(None))

    with pytest.raises(HTTPException) as exc_info:
        await get_lesson_plan(
            plan_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            db=mock_db,
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# edit_lesson_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_lesson_plan_when_generated_then_stores_edits():
    from app.schemas.lesson_plans import LessonPlanEditRequest

    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id, status="GENERATED")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),
            _scalar(class_),
        ]
    )
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    body = LessonPlanEditRequest(teacher_tips="Circulate during group work.")
    await edit_lesson_plan(
        plan_id=plan.id,
        teacher_id=teacher_id,
        school_id=school_id,
        body=body,
        db=mock_db,
    )

    assert plan.status == "EDITED"
    assert plan.teacher_edits.get("teacher_tips") == "Circulate during group work."


@pytest.mark.asyncio
async def test_edit_lesson_plan_when_generating_then_raises_409():
    from app.schemas.lesson_plans import LessonPlanEditRequest

    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id, status="GENERATING")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),
            _scalar(class_),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await edit_lesson_plan(
            plan_id=plan.id,
            teacher_id=teacher_id,
            school_id=school_id,
            body=LessonPlanEditRequest(starter_10min="x"),
            db=mock_db,
        )

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# update_lesson_plan_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_lesson_plan_status_when_generated_to_used_then_succeeds():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id, status="GENERATED")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),
            _scalar(class_),
        ]
    )
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    await update_lesson_plan_status(
        plan_id=plan.id,
        teacher_id=teacher_id,
        school_id=school_id,
        new_status="USED",
        db=mock_db,
    )

    assert plan.status == "USED"


@pytest.mark.asyncio
async def test_update_lesson_plan_status_when_invalid_transition_then_raises_422():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id, status="GENERATING")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),
            _scalar(class_),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_lesson_plan_status(
            plan_id=plan.id,
            teacher_id=teacher_id,
            school_id=school_id,
            new_status="USED",
            db=mock_db,
        )

    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _to_response — teacher_edits override generated_plan
# ---------------------------------------------------------------------------


def test_to_response_when_teacher_edits_present_then_merges():
    plan = _make_plan(status="EDITED")
    plan.generated_plan = {"starter_10min": "original", "homework": "original hw"}
    plan.teacher_edits = {"starter_10min": "edited"}

    response = _to_response(plan, focus_subtopics=[])

    assert response.generated_plan is not None
    assert response.generated_plan["starter_10min"] == "edited"
    assert response.generated_plan["homework"] == "original hw"


def test_to_response_when_no_content_then_generated_plan_is_none():
    plan = _make_plan(status="GENERATING")
    plan.generated_plan = {}
    plan.teacher_edits = None

    response = _to_response(plan, focus_subtopics=[])

    assert response.generated_plan is None
