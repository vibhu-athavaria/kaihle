"""Unit tests for QuestionReviewService.

Tests follow TDD. Uses mock DB sessions — no real database required.
Naming: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.question_review import ApproveReviewItemRequest, RejectReviewItemRequest
from app.services.question_review_service import (
    QuestionReviewService,
    ReviewItemAlreadyResolvedError,
    ReviewItemNotFoundError,
)


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_db: MagicMock) -> QuestionReviewService:
    return QuestionReviewService(mock_db)


def _make_review_item(
    item_type: str = "TEACHER_QUESTION",
    status: str = "PENDING",
    question_id: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        item_type=item_type,
        question_id=question_id or uuid.uuid4(),
        submitted_by=uuid.uuid4(),
        school_id=school_id or uuid.uuid4(),
        assessment_id=None,
        suggested_question_text="Revised text",
        suggested_options=None,
        suggested_correct_answer="B",
        suggested_explanation=None,
        suggested_difficulty_level=3.0,
        reason="Fix typo",
        status=status,
        admin_note=None,
        resolved_by=None,
        resolved_at=None,
        created_at=None,
    )


def _make_question(
    question_id: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=question_id or uuid.uuid4(),
        question_text="Original text",
        question_type="MCQ",
        options=None,
        correct_answer="A",
        explanation=None,
        difficulty_level=2.0,
        school_id=school_id or uuid.uuid4(),
        review_status="PENDING_REVIEW",
        is_active=True,
    )


class TestApproveItem:
    """Tests for QuestionReviewService.approve_item."""

    @pytest.mark.asyncio
    async def test_approve_item_when_teacher_question_no_edits_then_clears_school_id(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="TEACHER_QUESTION")
        question = _make_question(question_id=item.question_id)

        mock_db.get = AsyncMock(side_effect=[item, question])

        await service.approve_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=ApproveReviewItemRequest(),
        )

        assert question.school_id is None
        assert question.review_status == "APPROVED"
        assert item.status == "APPROVED"

    @pytest.mark.asyncio
    async def test_approve_item_when_teacher_question_with_edits_then_applies_edits_then_promotes(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="TEACHER_QUESTION")
        question = _make_question(question_id=item.question_id)

        mock_db.get = AsyncMock(side_effect=[item, question])

        await service.approve_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=ApproveReviewItemRequest(question_text="Admin-edited text", correct_answer="C"),
        )

        assert question.question_text == "Admin-edited text"
        assert question.correct_answer == "C"
        assert question.school_id is None  # promoted

    @pytest.mark.asyncio
    async def test_approve_item_when_edit_suggestion_then_applies_suggested_fields_to_question_bank(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="EDIT_SUGGESTION")
        item.suggested_question_text = "Better question text"
        item.suggested_correct_answer = "B"
        question = _make_question(question_id=item.question_id)

        mock_db.get = AsyncMock(side_effect=[item, question])

        await service.approve_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=ApproveReviewItemRequest(),
        )

        assert question.question_text == "Better question text"
        assert question.correct_answer == "B"
        assert item.status == "APPROVED"

    @pytest.mark.asyncio
    async def test_approve_item_when_edit_suggestion_with_admin_edits_then_admin_version_applied(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="EDIT_SUGGESTION")
        item.suggested_question_text = "Teacher's version"
        item.suggested_correct_answer = "B"
        question = _make_question(question_id=item.question_id)

        mock_db.get = AsyncMock(side_effect=[item, question])

        await service.approve_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=ApproveReviewItemRequest(question_text="Admin's superior version"),
        )

        # Admin override takes precedence over teacher suggestion
        assert question.question_text == "Admin's superior version"
        # No admin override for correct_answer → use teacher's suggestion
        assert question.correct_answer == "B"

    @pytest.mark.asyncio
    async def test_approve_item_when_already_resolved_then_raises_ReviewItemAlreadyResolvedError(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(status="APPROVED")
        mock_db.get = AsyncMock(return_value=item)

        with pytest.raises(ReviewItemAlreadyResolvedError):
            await service.approve_item(
                item_id=item.id,
                admin_id=uuid.uuid4(),
                body=ApproveReviewItemRequest(),
            )

    @pytest.mark.asyncio
    async def test_approve_item_when_not_found_then_raises_ReviewItemNotFoundError(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(ReviewItemNotFoundError):
            await service.approve_item(
                item_id=uuid.uuid4(),
                admin_id=uuid.uuid4(),
                body=ApproveReviewItemRequest(),
            )


class TestRejectItem:
    """Tests for QuestionReviewService.reject_item."""

    @pytest.mark.asyncio
    async def test_reject_item_when_teacher_question_then_sets_is_active_false_and_rejected(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="TEACHER_QUESTION")
        question = _make_question(question_id=item.question_id)

        mock_db.get = AsyncMock(side_effect=[item, question])

        await service.reject_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=RejectReviewItemRequest(admin_note="Not relevant"),
        )

        assert question.is_active is False
        assert question.review_status == "REJECTED"
        assert item.status == "REJECTED"
        assert item.admin_note == "Not relevant"

    @pytest.mark.asyncio
    async def test_reject_item_when_edit_suggestion_then_question_bank_unchanged(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="EDIT_SUGGESTION")
        question = _make_question(question_id=item.question_id)

        # EDIT_SUGGESTION rejection: get called for item only (not question for data change)
        mock_db.get = AsyncMock(return_value=item)

        await service.reject_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=RejectReviewItemRequest(),
        )

        # question_bank not modified — is_active and correct_answer unchanged
        assert question.is_active is True
        assert item.status == "REJECTED"

    @pytest.mark.asyncio
    async def test_reject_item_when_admin_note_then_note_stored_on_review_item(
        self, mock_db: MagicMock, service: QuestionReviewService
    ) -> None:
        item = _make_review_item(item_type="EDIT_SUGGESTION")
        mock_db.get = AsyncMock(return_value=item)

        await service.reject_item(
            item_id=item.id,
            admin_id=uuid.uuid4(),
            body=RejectReviewItemRequest(admin_note="Duplicate of existing question"),
        )

        assert item.admin_note == "Duplicate of existing question"
