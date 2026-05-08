"""Unit tests for lesson plan Celery task internals."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_plan(status: str = "GENERATING") -> MagicMock:
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.status = status
    plan.generated_plan = None
    plan.raw_llm_output = None
    plan.failure_code = None
    plan.failure_reason = None
    plan.class_context_snapshot = None
    return plan


def _make_valid_content() -> dict:
    return {
        "lesson_hook": "Test hook",
        "time_breakdown": {
            "starter_minutes": 6,
            "intro_minutes": 9,
            "activity_minutes": 30,
            "exit_ticket_minutes": 6,
            "plenary_minutes": 9,
        },
        "learning_objectives": ["I can do X"],
        "key_concepts": [],
        "group_activities": {
            "foundation": {"description": "a", "stuck_prompt": "b"},
            "core": {"description": "c", "stuck_prompt": "d"},
            "extension": {"description": "e", "stuck_prompt": "f"},
        },
        "resources_needed": [],
        "exit_ticket": {"questions": []},
        "starter": {"duration_minutes": 6, "activity": "test"},
        "plenary": {"duration_minutes": 9, "activity": "test"},
        "prior_knowledge": "test",
        "homework": None,
    }


def _build_mock_db(plan: MagicMock, class_id: uuid.UUID | None = None) -> AsyncMock:
    """Build a mock DB session with standard execute side effects."""
    mock_class = MagicMock()
    mock_class.id = class_id or uuid.uuid4()
    mock_class.name = "7A Science"
    mock_class.grade_id = uuid.uuid4()
    mock_class.subject_id = uuid.uuid4()

    grade = MagicMock()
    grade.name = "Grade 7"
    subject = MagicMock()
    subject.name = "Science"

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    class_result = MagicMock()
    class_result.scalar_one_or_none.return_value = mock_class

    enrolled_ids_result = MagicMock()
    enrolled_ids_result.all.return_value = [(uuid.uuid4(),), (uuid.uuid4(),)]

    profiles_result = MagicMock()
    profiles = [
        MagicMock(
            modality_scores={"visual": 0.8, "auditory": 0.3, "reading_writing": 0.5, "kinesthetic": 0.4},
            interests=["football", "gaming"],
        ),
    ]
    profiles_result.scalars.return_value.all.return_value = profiles

    subtopics_result = MagicMock()
    subtopics_result.scalars.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            plan_result,
            class_result,
            enrolled_ids_result,
            profiles_result,
            subtopics_result,
        ]
    )
    mock_db.get = AsyncMock(side_effect=[grade, subject])
    mock_db.commit = AsyncMock()
    return mock_db


@pytest.mark.asyncio
async def test_generate_when_llm_returns_valid_json_then_stores_plan_and_raw_output() -> None:
    """Happy path: valid LLM JSON → generated_plan set, raw_llm_output stored, status=GENERATED."""
    from app.models.lesson_plan import LessonPlanStatus
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    mock_db = _build_mock_db(plan)
    valid_content = _make_valid_content()
    response_text = json.dumps(valid_content)

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email") as mock_email,
        patch("app.ai.providers.router.complete", new=AsyncMock(return_value=response_text)),
        patch("app.tasks.lesson_plan_tasks._fetch_teacher_email", new=AsyncMock(return_value="teacher@test.com")),
    ):
        await _generate(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[str(uuid.uuid4())],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.generated_plan == valid_content
    assert plan.raw_llm_output == response_text
    assert plan.status == LessonPlanStatus.GENERATED
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_generate_when_llm_returns_invalid_json_twice_then_archives_plan() -> None:
    """When LLM returns invalid JSON on both attempts, plan is archived with JSON_PARSE_FAILED."""
    from app.models.lesson_plan import LessonPlanFailureCode, LessonPlanStatus
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    mock_db = _build_mock_db(plan)

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_failed_email") as mock_fail_email,
        patch("app.ai.providers.router.complete", new=AsyncMock(return_value="not valid json at all")),
        patch("app.tasks.lesson_plan_tasks._fetch_teacher_email", new=AsyncMock(return_value="t@test.com")),
    ):
        await _generate(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.ARCHIVED
    assert plan.failure_code == LessonPlanFailureCode.JSON_PARSE_FAILED
    mock_fail_email.assert_called_once()


@pytest.mark.asyncio
async def test_generate_when_first_attempt_fails_but_retry_succeeds_then_generated() -> None:
    """When first attempt is invalid JSON but correction retry returns valid JSON, plan is GENERATED."""
    from app.models.lesson_plan import LessonPlanStatus
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    mock_db = _build_mock_db(plan)
    valid_text = json.dumps(_make_valid_content())

    complete_mock = AsyncMock(side_effect=["not valid json", valid_text])

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"),
        patch("app.ai.providers.router.complete", new=complete_mock),
        patch("app.tasks.lesson_plan_tasks._fetch_teacher_email", new=AsyncMock(return_value="t@test.com")),
    ):
        await _generate(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.GENERATED
    assert complete_mock.call_count == 2


def test_compute_class_context_when_profiles_empty_then_returns_empty_context() -> None:
    """When no learning profiles exist, context has empty distribution and zero count."""
    from app.tasks.lesson_plan_tasks import _compute_class_context

    ctx = _compute_class_context([])
    assert ctx["student_count"] == 0
    assert ctx["modality_distribution"] == {}
    assert ctx["top_interests"] == []


def test_compute_class_context_when_profiles_given_then_averages_modalities() -> None:
    """Modality scores are averaged across all profiles."""
    from app.tasks.lesson_plan_tasks import _compute_class_context

    p1 = MagicMock(modality_scores={"visual": 0.8, "auditory": 0.4}, interests=["football"])
    p2 = MagicMock(modality_scores={"visual": 0.6, "auditory": 0.6}, interests=["gaming", "football"])

    ctx = _compute_class_context([p1, p2])

    assert ctx["student_count"] == 2
    assert ctx["modality_distribution"]["visual"] == pytest.approx(0.7)
    assert ctx["modality_distribution"]["auditory"] == pytest.approx(0.5)
    assert "football" in ctx["top_interests"]


@pytest.mark.asyncio
async def test_generate_when_plan_not_found_then_returns_early() -> None:
    """When lesson plan row is missing, _generate returns without archiving."""
    from app.tasks.lesson_plan_tasks import _generate

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=plan_result)
    mock_db.commit = AsyncMock()

    await _generate(
        lesson_plan_id=str(uuid.uuid4()),
        class_id=str(uuid.uuid4()),
        focus_subtopic_ids=[],
        duration_minutes=60,
        teacher_id=str(uuid.uuid4()),
        db=mock_db,
    )

    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_generate_when_class_not_found_then_archives_with_class_not_found_code() -> None:
    """When class row is missing, plan is archived with CLASS_NOT_FOUND."""
    from app.models.lesson_plan import LessonPlanFailureCode, LessonPlanStatus
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    class_result = MagicMock()
    class_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[plan_result, class_result])
    mock_db.commit = AsyncMock()

    with patch("app.tasks.lesson_plan_tasks.send_lesson_plan_failed_email"):
        await _generate(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.ARCHIVED
    assert plan.failure_code == LessonPlanFailureCode.CLASS_NOT_FOUND


@pytest.mark.asyncio
async def test_generate_when_llm_auth_error_then_archives_with_auth_code() -> None:
    """LiteLLM AuthenticationError → plan archived with LLM_AUTH_ERROR, no retry."""
    import litellm

    from app.models.lesson_plan import LessonPlanFailureCode, LessonPlanStatus
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    mock_db = _build_mock_db(plan)

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_failed_email"),
        patch(
            "app.ai.providers.router.complete",
            new=AsyncMock(side_effect=litellm.AuthenticationError("bad key", llm_provider="openai", model="x")),
        ),
    ):
        await _generate(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.ARCHIVED
    assert plan.failure_code == LessonPlanFailureCode.LLM_AUTH_ERROR


@pytest.mark.asyncio
async def test_generate_when_rate_limit_error_then_reraises_for_celery_retry() -> None:
    """LiteLLM RateLimitError is re-raised so Celery can retry — plan stays GENERATING."""
    import litellm

    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    mock_db = _build_mock_db(plan)

    with patch(
        "app.ai.providers.router.complete",
        new=AsyncMock(side_effect=litellm.RateLimitError("rate limited", llm_provider="openai", model="x")),
    ):
        with pytest.raises(litellm.RateLimitError):
            await _generate(
                lesson_plan_id=str(plan.id),
                class_id=str(uuid.uuid4()),
                focus_subtopic_ids=[],
                duration_minutes=60,
                teacher_id=str(uuid.uuid4()),
                db=mock_db,
            )

    # Plan must remain in GENERATING — Celery will retry
    assert plan.status == "GENERATING"
    mock_db.commit.assert_not_called()
