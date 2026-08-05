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


def _make_school(city: str | None = "Bangkok", country: str | None = "Thailand") -> MagicMock:
    school = MagicMock()
    school.city = city
    school.country = country
    return school


def _build_mock_db(
    plan: MagicMock,
    class_id: uuid.UUID | None = None,
    school: MagicMock | None = None,
) -> AsyncMock:
    """Build a mock DB session with standard execute side effects."""
    mock_class = MagicMock()
    mock_class.id = class_id or uuid.uuid4()
    mock_class.name = "7A Science"
    mock_class.grade_id = uuid.uuid4()
    mock_class.subject_id = uuid.uuid4()
    mock_class.school_id = uuid.uuid4()

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
    mock_db.get = AsyncMock(side_effect=[grade, subject, school or _make_school()])
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


# ---------------------------------------------------------------------------
# School location in prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_when_school_has_city_and_country_then_prompt_includes_location() -> None:
    """School city + country are injected into the rendered prompt sent to the LLM."""
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    school = _make_school(city="Kuala Lumpur", country="Malaysia")
    mock_db = _build_mock_db(plan, school=school)
    valid_text = json.dumps(_make_valid_content())

    captured_calls: list = []

    async def _capture_complete(**kwargs: object) -> str:
        captured_calls.append(kwargs)
        return valid_text

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"),
        patch("app.ai.providers.router.complete", new=_capture_complete),
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

    assert captured_calls, "LLM was never called"
    prompt_text = captured_calls[0]["messages"][0]["content"]
    assert "Kuala Lumpur" in prompt_text
    assert "Malaysia" in prompt_text


@pytest.mark.asyncio
async def test_generate_when_school_has_no_location_then_prompt_omits_location_section() -> None:
    """When school city and country are both None, no location block appears in the prompt."""
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    school = _make_school(city=None, country=None)
    mock_db = _build_mock_db(plan, school=school)
    valid_text = json.dumps(_make_valid_content())

    captured_calls: list = []

    async def _capture_complete(**kwargs: object) -> str:
        captured_calls.append(kwargs)
        return valid_text

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"),
        patch("app.ai.providers.router.complete", new=_capture_complete),
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

    assert captured_calls, "LLM was never called"
    prompt_text = captured_calls[0]["messages"][0]["content"]
    assert "School location" not in prompt_text


@pytest.mark.asyncio
async def test_generate_when_school_has_country_only_then_prompt_includes_country_without_none() -> None:
    """When only country is set (city is None), prompt shows country and never the word 'None'."""
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    school = _make_school(city=None, country="Singapore")
    mock_db = _build_mock_db(plan, school=school)
    valid_text = json.dumps(_make_valid_content())

    captured_calls: list = []

    async def _capture_complete(**kwargs: object) -> str:
        captured_calls.append(kwargs)
        return valid_text

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"),
        patch("app.ai.providers.router.complete", new=_capture_complete),
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

    assert captured_calls, "LLM was never called"
    prompt_text = captured_calls[0]["messages"][0]["content"]
    assert "Singapore" in prompt_text
    assert "None" not in prompt_text


@pytest.mark.asyncio
async def test_generate_when_school_has_city_only_then_prompt_includes_city_without_none() -> None:
    """When only city is set (country is None), prompt shows city and never the word 'None'."""
    from app.tasks.lesson_plan_tasks import _generate

    plan = _make_plan()
    school = _make_school(city="Jakarta", country=None)
    mock_db = _build_mock_db(plan, school=school)
    valid_text = json.dumps(_make_valid_content())

    captured_calls: list = []

    async def _capture_complete(**kwargs: object) -> str:
        captured_calls.append(kwargs)
        return valid_text

    with (
        patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"),
        patch("app.ai.providers.router.complete", new=_capture_complete),
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

    assert captured_calls, "LLM was never called"
    prompt_text = captured_calls[0]["messages"][0]["content"]
    assert "Jakarta" in prompt_text
    assert "None" not in prompt_text


def test_prompt_skeleton_when_rendered_then_is_parseable_json() -> None:
    """Regression: the output skeleton shown to the LLM must itself be valid JSON.

    It previously used bare <int> placeholders, which models copied verbatim into
    their response and which json.loads rejects with "Expecting value".
    """
    from app.tasks.lesson_plan_tasks import _extract_json_object, _jinja_env

    rendered = _jinja_env.get_template("lesson_plan.jinja2").render(
        class_name="Science Grade 7",
        subject_name="Science",
        grade_name="Grade 7",
        student_count=20,
        duration_minutes=60,
        subtopics=[{"name": "Forces", "learning_objective": "Describe forces"}],
        modality_distribution={"visual": 0.6, "auditory": 0.4},
        top_interests=["football"],
        school_location={"city": "Bangkok", "country": "Thailand"},
    )

    skeleton = json.loads(_extract_json_object(rendered))

    assert skeleton["time_breakdown"]["starter_minutes"] == 6
    assert skeleton["time_breakdown"]["activity_minutes"] == 30
    assert isinstance(skeleton["key_concepts"][0]["duration_minutes"], int)


def test_try_validate_when_response_is_bare_json_then_parses() -> None:
    """Plain JSON with no wrapping is accepted."""
    from app.tasks.lesson_plan_tasks import _try_validate

    parsed, error = _try_validate(json.dumps(_make_valid_content()))

    assert error == ""
    assert parsed is not None
    assert parsed["lesson_hook"] == "Test hook"


def test_try_validate_when_response_is_fenced_then_parses() -> None:
    """Markdown-fenced JSON is recovered instead of burning a correction retry."""
    from app.tasks.lesson_plan_tasks import _try_validate

    raw = "```json\n" + json.dumps(_make_valid_content()) + "\n```"

    parsed, error = _try_validate(raw)

    assert error == ""
    assert parsed is not None


def test_try_validate_when_response_has_surrounding_prose_then_parses() -> None:
    """Prose before and after the object is stripped."""
    from app.tasks.lesson_plan_tasks import _try_validate

    raw = "Here is the plan:\n" + json.dumps(_make_valid_content()) + "\nLet me know if you want changes."

    parsed, error = _try_validate(raw)

    assert error == ""
    assert parsed is not None


def test_try_validate_when_response_has_placeholder_token_then_returns_parse_error() -> None:
    """A bare <int> placeholder is still reported as a parse error, not silently accepted."""
    from app.tasks.lesson_plan_tasks import _try_validate

    content = _make_valid_content()
    raw = json.dumps(content).replace('"starter_minutes": 6', '"starter_minutes": <int>')

    parsed, error = _try_validate(raw)

    assert parsed is None
    assert "JSON parse error" in error
