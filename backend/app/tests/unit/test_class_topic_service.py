"""Unit tests for ClassTopicService.

Tests all methods: list_topics, add_topic, update_topic, remove_topic,
reorder_topics, list_curriculum_topics_for_class.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.class_topic import ClassTopicAdd, ClassTopicReorder, ClassTopicUpdate
from app.services.class_topic_service import (
    ClassTopicNotFoundError,
    ClassTopicService,
    DuplicateClassTopicError,
)


def _make_db() -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    return db


def _make_class_topic(
    class_id: uuid.UUID | None = None,
    curriculum_topic_id: uuid.UUID | None = None,
    sequence_order: int = 0,
    is_covered: bool = False,
) -> MagicMock:
    ct = MagicMock()
    ct.id = uuid.uuid4()
    ct.class_id = class_id or uuid.uuid4()
    ct.curriculum_topic_id = curriculum_topic_id or uuid.uuid4()
    ct.sequence_order = sequence_order
    ct.is_covered = is_covered
    ct.updated_at = None
    return ct


def _mock_execute_returning(db: AsyncMock, result_value: object) -> None:
    result = MagicMock()
    result.all.return_value = result_value
    result.scalar_one_or_none.return_value = result_value
    result.scalars.return_value.all.return_value = result_value
    db.execute = AsyncMock(return_value=result)


# ─── list_topics ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_topics_when_no_topics_then_returns_empty_list() -> None:
    db = _make_db()
    result = MagicMock()
    result.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    service = ClassTopicService(db)

    topics = await service.list_topics(uuid.uuid4())

    assert topics == []


@pytest.mark.asyncio
async def test_list_topics_when_topics_exist_then_returns_response_list() -> None:
    db = _make_db()
    class_id = uuid.uuid4()
    curriculum_topic_id = uuid.uuid4()

    ct = _make_class_topic(class_id=class_id, curriculum_topic_id=curriculum_topic_id)

    row = MagicMock()
    row.ClassTopic = ct
    row.topic_id = uuid.uuid4()
    row.topic_name = "Algebra"
    row.subtopic_count = 3

    result = MagicMock()
    result.all.return_value = [row]
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    topics = await service.list_topics(class_id)

    assert len(topics) == 1
    assert topics[0].topic_name == "Algebra"
    assert topics[0].subtopic_count == 3
    assert topics[0].class_id == class_id


# ─── add_topic ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_topic_when_curriculum_topic_not_found_then_raises_not_found_error() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    body = ClassTopicAdd(curriculum_topic_id=uuid.uuid4(), sequence_order=0)

    with pytest.raises(ClassTopicNotFoundError):
        await service.add_topic(uuid.uuid4(), uuid.uuid4(), body)


@pytest.mark.asyncio
async def test_add_topic_when_already_in_class_then_raises_duplicate_error() -> None:
    db = _make_db()
    curriculum_topic_id = uuid.uuid4()

    fake_ct = MagicMock()
    fake_ct.id = curriculum_topic_id

    existing = MagicMock()

    # First execute: curriculum_topic found; Second execute: existing class_topic found
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_ct
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = existing

    db.execute = AsyncMock(side_effect=[result1, result2])

    service = ClassTopicService(db)
    body = ClassTopicAdd(curriculum_topic_id=curriculum_topic_id, sequence_order=0)

    with pytest.raises(DuplicateClassTopicError):
        await service.add_topic(uuid.uuid4(), uuid.uuid4(), body)


@pytest.mark.asyncio
async def test_add_topic_when_valid_then_returns_response_with_topic_name() -> None:
    db = _make_db()
    curriculum_topic_id = uuid.uuid4()
    class_id = uuid.uuid4()
    school_id = uuid.uuid4()

    fake_ct = MagicMock()
    fake_ct.id = curriculum_topic_id

    # result1: curriculum_topic found
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_ct

    # result2: no existing class_topic
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None

    # result3: topic_id + topic_name + subtopic_count
    topic_row = MagicMock()
    topic_row.topic_id = uuid.uuid4()
    topic_row.topic_name = "Linear Equations"
    topic_row.subtopic_count = 5
    result3 = MagicMock()
    result3.one.return_value = topic_row

    db.execute = AsyncMock(side_effect=[result1, result2, result3])

    # Give the ClassTopic instance a UUID when add() is called (simulates flush assigning id)
    added_instances: list = []

    def _capture_add(instance: object) -> None:
        added_instances.append(instance)
        # Assign a real uuid so ClassTopicResponse validation passes
        instance.id = uuid.uuid4()  # type: ignore[attr-defined]
        instance.class_id = class_id  # type: ignore[attr-defined]
        instance.curriculum_topic_id = curriculum_topic_id  # type: ignore[attr-defined]
        instance.sequence_order = 1  # type: ignore[attr-defined]
        instance.is_covered = False  # type: ignore[attr-defined]

    db.add = _capture_add

    service = ClassTopicService(db)
    body = ClassTopicAdd(curriculum_topic_id=curriculum_topic_id, sequence_order=1)
    response = await service.add_topic(class_id, school_id, body)

    assert response.topic_name == "Linear Equations"
    assert response.subtopic_count == 5
    assert len(added_instances) == 1
    db.flush.assert_called_once()


# ─── update_topic ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_topic_when_class_topic_not_found_then_raises_not_found_error() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    with pytest.raises(ClassTopicNotFoundError):
        await service.update_topic(uuid.uuid4(), uuid.uuid4(), ClassTopicUpdate(is_covered=True))


@pytest.mark.asyncio
async def test_update_topic_when_is_covered_set_then_field_updated() -> None:
    db = _make_db()
    ct = _make_class_topic()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = ct

    topic_row = MagicMock()
    topic_row.topic_id = uuid.uuid4()
    topic_row.topic_name = "Fractions"
    topic_row.subtopic_count = 2
    result2 = MagicMock()
    result2.one.return_value = topic_row

    db.execute = AsyncMock(side_effect=[result1, result2])

    service = ClassTopicService(db)
    response = await service.update_topic(ct.class_id, ct.id, ClassTopicUpdate(is_covered=True))

    assert ct.is_covered is True
    assert response.topic_name == "Fractions"
    db.flush.assert_called_once()


# ─── remove_topic ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_topic_when_not_found_then_raises_not_found_error() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    with pytest.raises(ClassTopicNotFoundError):
        await service.remove_topic(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_remove_topic_when_found_then_deletes_and_flushes() -> None:
    db = _make_db()
    ct = _make_class_topic()

    result = MagicMock()
    result.scalar_one_or_none.return_value = ct
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    await service.remove_topic(ct.class_id, ct.id)

    db.delete.assert_called_once_with(ct)
    db.flush.assert_called_once()


# ─── reorder_topics ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reorder_topics_when_topic_id_not_found_then_raises_not_found_error() -> None:
    db = _make_db()
    class_id = uuid.uuid4()
    unknown_id = uuid.uuid4()

    result1 = MagicMock()
    result1.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result1)

    service = ClassTopicService(db)
    body = ClassTopicReorder(items=[(unknown_id, 0)])

    with pytest.raises(ClassTopicNotFoundError):
        await service.reorder_topics(class_id, body)


@pytest.mark.asyncio
async def test_reorder_topics_when_valid_then_updates_sequence_orders() -> None:
    db = _make_db()
    class_id = uuid.uuid4()
    ct1 = _make_class_topic(class_id=class_id, sequence_order=1)
    ct2 = _make_class_topic(class_id=class_id, sequence_order=0)

    # First execute: fetch topics_by_id
    result1 = MagicMock()
    result1.scalars.return_value.all.return_value = [ct1, ct2]
    # Second execute: list_topics (re-query after reorder)
    empty_list_result = MagicMock()
    empty_list_result.all.return_value = []
    db.execute = AsyncMock(side_effect=[result1, empty_list_result])

    service = ClassTopicService(db)
    body = ClassTopicReorder(items=[(ct1.id, 0), (ct2.id, 1)])
    await service.reorder_topics(class_id, body)

    assert ct1.sequence_order == 0
    assert ct2.sequence_order == 1
    db.flush.assert_called_once()


# ─── list_curriculum_topics_for_class ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_curriculum_topics_for_class_when_class_not_found_then_raises() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    with pytest.raises(ClassTopicNotFoundError):
        await service.list_curriculum_topics_for_class(uuid.uuid4())


@pytest.mark.asyncio
async def test_list_curriculum_topics_for_class_when_none_existing_then_returns_all_available() -> None:
    db = _make_db()
    class_id = uuid.uuid4()

    fake_class = MagicMock()
    fake_class.curriculum_id = uuid.uuid4()
    fake_class.subject_id = uuid.uuid4()
    fake_class.grade_id = uuid.uuid4()

    # result1: class found
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class

    # result2: existing class_topic ids (none)
    result2 = MagicMock()
    result2.scalars.return_value.all.return_value = []

    # result3: available curriculum topics
    ct_row = MagicMock()
    ct_row.CurriculumTopic = MagicMock()
    ct_row.CurriculumTopic.id = uuid.uuid4()
    ct_row.CurriculumTopic.sequence_order = 0
    ct_row.topic_name = "Algebra"
    ct_row.subtopic_count = 3
    result3 = MagicMock()
    result3.all.return_value = [ct_row]

    db.execute = AsyncMock(side_effect=[result1, result2, result3])

    service = ClassTopicService(db)
    topics = await service.list_curriculum_topics_for_class(class_id)

    assert len(topics) == 1
    assert topics[0]["topic_name"] == "Algebra"
    assert topics[0]["subtopic_count"] == 3


# ─── list_topics_for_diagnostic ───────────────────────────────────────────────


def _make_topic_row(name: str, grade_level: int, subtopic_count: int = 2) -> MagicMock:
    row = MagicMock()
    row.curriculum_topic_id = uuid.uuid4()
    row.topic_name = name
    row.grade_level = grade_level
    row.subtopic_count = subtopic_count
    return row


@pytest.mark.asyncio
async def test_list_topics_for_diagnostic_when_class_not_found_then_raises() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = ClassTopicService(db)
    with pytest.raises(ClassTopicNotFoundError):
        await service.list_topics_for_diagnostic(uuid.uuid4())


@pytest.mark.asyncio
async def test_list_topics_for_diagnostic_when_same_curriculum_then_returns_both_grades() -> None:
    db = _make_db()
    class_id = uuid.uuid4()

    fake_class = MagicMock()
    fake_class.curriculum_id = uuid.uuid4()
    fake_class.subject_id = uuid.uuid4()
    fake_class.grade_id = uuid.uuid4()
    fake_class.school_id = uuid.uuid4()

    # execute call 1: fetch class
    r_class = MagicMock()
    r_class.scalar_one_or_none.return_value = fake_class

    # execute call 2: fetch current grade level
    r_level = MagicMock()
    r_level.scalar_one_or_none.return_value = 9

    # execute call 3: fetch prev grade id
    prev_grade_id = uuid.uuid4()
    r_prev_id = MagicMock()
    r_prev_id.scalar_one_or_none.return_value = prev_grade_id

    # execute call 4: current grade topics
    curr_row = _make_topic_row("Functions", grade_level=9)
    r_curr = MagicMock()
    r_curr.all.return_value = [curr_row]

    # execute call 5: previous grade topics
    prev_row = _make_topic_row("Algebra", grade_level=8)
    r_prev = MagicMock()
    r_prev.all.return_value = [prev_row]

    db.execute = AsyncMock(side_effect=[r_class, r_level, r_prev_id, r_curr, r_prev])

    service = ClassTopicService(db)
    result = await service.list_topics_for_diagnostic(class_id)

    assert result["current_grade_level"] == 9
    assert result["previous_grade_level"] == 8
    assert len(result["current_grade_topics"]) == 1
    assert result["current_grade_topics"][0]["topic_name"] == "Functions"
    assert len(result["previous_grade_topics"]) == 1
    assert result["previous_grade_topics"][0]["topic_name"] == "Algebra"


@pytest.mark.asyncio
async def test_list_topics_for_diagnostic_when_grade_level_1_then_no_previous_query() -> None:
    """At grade level 1 (no prior grade), previous query must be skipped entirely."""
    db = _make_db()

    fake_class = MagicMock()
    fake_class.curriculum_id = uuid.uuid4()
    fake_class.subject_id = uuid.uuid4()
    fake_class.grade_id = uuid.uuid4()
    fake_class.school_id = uuid.uuid4()

    r_class = MagicMock()
    r_class.scalar_one_or_none.return_value = fake_class

    r_level = MagicMock()
    r_level.scalar_one_or_none.return_value = 1  # no prev grade

    curr_row = _make_topic_row("Numbers", grade_level=1)
    r_curr = MagicMock()
    r_curr.all.return_value = [curr_row]

    # Only 3 execute calls expected — no prev-grade-id lookup, no prev-topics query
    db.execute = AsyncMock(side_effect=[r_class, r_level, r_curr])

    service = ClassTopicService(db)
    result = await service.list_topics_for_diagnostic(uuid.uuid4())

    assert result["previous_grade_topics"] == []
    assert len(result["current_grade_topics"]) == 1
    assert db.execute.call_count == 3
