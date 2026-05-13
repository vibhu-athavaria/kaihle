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
    list_teacher_lesson_plans,
    regenerate_lesson_plan,
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
    p.duration_minutes = 45
    p.focus_subtopic_ids = []
    p.class_context_snapshot = {}
    p.generated_plan = {"starter_10min": "intro"}
    p.teacher_edits = None
    p.generated_at = datetime.now(UTC)
    p.failure_code = None
    p.failure_reason = None
    return p


def _rows(values):
    """Mock db.execute result for queries returning .all() rows (used by _fetch_class_names)."""
    r = MagicMock()
    r.all.return_value = values
    return r


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
            _scalars([]),  # _build_class_context_snapshot — GapState rows
            _scalars([]),  # _build_class_context_snapshot — subtopics
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
            "app.services.lesson_plan_service.generate_lesson_plan_task",
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
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
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
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
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
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
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
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
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

    response = _to_response(plan, focus_subtopics=[], class_name="")

    assert response.generated_plan is not None
    assert response.generated_plan["starter_10min"] == "edited"
    assert response.generated_plan["homework"] == "original hw"


def test_to_response_when_no_content_then_generated_plan_is_none():
    plan = _make_plan(status="GENERATING")
    plan.generated_plan = {}
    plan.teacher_edits = None

    response = _to_response(plan, focus_subtopics=[], class_name="")

    assert response.generated_plan is None


# ---------------------------------------------------------------------------
# list_teacher_lesson_plans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_teacher_lesson_plans_when_no_class_filter_then_returns_all_plans():
    teacher_id = uuid.uuid4()
    plan1 = _make_plan(teacher_id=teacher_id)
    plan2 = _make_plan(teacher_id=teacher_id)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar_one(2),  # count
            _scalars([plan1, plan2]),  # list
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
        ]
    )

    page = await list_teacher_lesson_plans(
        teacher_id=teacher_id,
        school_id=uuid.uuid4(),
        page=1,
        page_size=10,
        db=mock_db,
    )

    assert page.total == 2
    assert len(page.data) == 2


@pytest.mark.asyncio
async def test_list_teacher_lesson_plans_when_class_filter_set_then_filters_results():
    teacher_id = uuid.uuid4()
    class_id = uuid.uuid4()
    plan = _make_plan(teacher_id=teacher_id, class_id=class_id)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar_one(1),
            _scalars([plan]),
            _scalars([]),
            _rows([]),
        ]
    )

    page = await list_teacher_lesson_plans(
        teacher_id=teacher_id,
        school_id=uuid.uuid4(),
        page=1,
        page_size=10,
        db=mock_db,
        class_id=class_id,
    )

    assert page.total == 1
    assert page.data[0].class_id == class_id


# ---------------------------------------------------------------------------
# regenerate_lesson_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_lesson_plan_when_plan_exists_then_resets_to_generating():
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    class_ = _make_class(teacher_id=teacher_id, school_id=school_id)
    plan = _make_plan(class_id=class_.id, teacher_id=teacher_id, status="ARCHIVED")
    plan.failure_code = "llm_unexpected_error"
    plan.failure_reason = "Some error"

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),  # _require_plan
            _scalar(class_),  # class school check
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
        ]
    )
    mock_db.commit = AsyncMock()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()

    with patch("app.services.lesson_plan_service.generate_lesson_plan_task", mock_task):
        await regenerate_lesson_plan(
            plan_id=plan.id,
            teacher_id=teacher_id,
            school_id=school_id,
            db=mock_db,
        )

    assert plan.status == "GENERATING"
    assert plan.failure_code is None
    assert plan.failure_reason is None
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_regenerate_lesson_plan_when_plan_not_found_then_raises_404():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar(None))

    with pytest.raises(HTTPException) as exc_info:
        await regenerate_lesson_plan(
            plan_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            db=mock_db,
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# _require_plan — school_id access control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_plan_when_plan_found_but_wrong_school_then_raises_403():
    """Plan exists and belongs to the teacher but class is in a different school."""
    teacher_id = uuid.uuid4()
    school_id = uuid.uuid4()
    plan = _make_plan(teacher_id=teacher_id)
    plan.class_id = uuid.uuid4()  # class belongs to other_school_id

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),  # plan found by teacher_id
            _scalar(None),  # class with (plan.class_id, school_id) not found → 403
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_lesson_plan(
            plan_id=plan.id,
            teacher_id=teacher_id,
            school_id=school_id,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_plan_when_school_id_none_then_skips_school_check():
    """school_id=None (KAIHLE_ADMIN) bypasses the class school verification."""
    teacher_id = uuid.uuid4()
    plan = _make_plan(teacher_id=teacher_id)
    plan.focus_subtopic_ids = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar(plan),  # _require_plan: plan found
            _scalars([]),  # _fetch_subtopic_context
            _rows([]),  # _fetch_class_names
        ]
    )

    # Should NOT raise — school_id=None means no class school check
    response = await get_lesson_plan(
        plan_id=plan.id,
        teacher_id=teacher_id,
        school_id=None,
        db=mock_db,
    )

    # Response returned successfully
    assert response is not None


# ---------------------------------------------------------------------------
# _fetch_subtopic_context — sorting and empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_subtopic_context_when_ids_out_of_order_then_sorts_by_input_order():
    """Results should be sorted to match the order of subtopic_ids, not DB order."""
    from app.services.lesson_plan_service import _fetch_subtopic_context

    s1 = uuid.uuid4()
    s2 = uuid.uuid4()
    s3 = uuid.uuid4()

    row1 = MagicMock()
    row1.id = s2
    row1.name = "Topic B"
    row1.topic_name = "Parent Topic"

    row2 = MagicMock()
    row2.id = s1
    row2.name = "Topic A"
    row2.topic_name = "Parent Topic"

    row3 = MagicMock()
    row3.id = s3
    row3.name = "Topic C"
    row3.topic_name = "Parent Topic"

    mock_db = AsyncMock()
    # rows returned in DB order (s3, s1, s2) — not matching input order
    mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row3, row1, row2])))

    result = await _fetch_subtopic_context([s1, s2, s3], mock_db)

    # Should be sorted by input order: s1, s2, s3
    assert result[0].subtopic_id == s1
    assert result[1].subtopic_id == s2
    assert result[2].subtopic_id == s3


@pytest.mark.asyncio
async def test_fetch_subtopic_context_when_empty_ids_then_returns_empty():
    """Returns [] immediately when subtopic_ids is empty — no DB query."""
    from app.services.lesson_plan_service import _fetch_subtopic_context

    mock_db = AsyncMock()
    result = await _fetch_subtopic_context([], mock_db)
    assert result == []
    mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_class_names — empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_class_names_when_empty_ids_then_returns_empty_dict():
    """Returns {} immediately when class_ids is empty — no DB query."""
    from app.services.lesson_plan_service import _fetch_class_names

    mock_db = AsyncMock()
    result = await _fetch_class_names([], mock_db)
    assert result == {}
    mock_db.execute.assert_not_called()
