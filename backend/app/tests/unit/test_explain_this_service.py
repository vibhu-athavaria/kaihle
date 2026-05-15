"""Unit tests for the explain_subtopic_question service function.

Tests cover:
- Input validation (question length > 500 chars → 422)
- Subtopic not found → 404
- Valid request yields SSE chunks including [DONE]
- Missing learning profile falls back to defaults gracefully
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.concept_guide_service import explain_subtopic_question

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SUBTOPIC_ID = uuid4()
_STUDENT_ID = uuid4()
_SCHOOL_ID = uuid4()


def _mock_subtopic_row(
    subtopic_name: str = "Linear Equations",
    topic_name: str = "Algebra",
    subject_name: str = "Mathematics",
    grade_level: int = 7,
) -> MagicMock:
    row = MagicMock()
    row.subtopic_name = subtopic_name
    row.topic_name = topic_name
    row.subject_name = subject_name
    row.grade_level = grade_level
    return row


def _mock_profile(
    modality_scores: dict | None = None,
    interests: list | None = None,
) -> MagicMock:
    profile = MagicMock()
    profile.modality_scores = modality_scores or {"visual": 0.9, "auditory": 0.3}
    profile.interests = interests or ["sports", "gaming"]
    return profile


async def _collect(gen: AsyncGenerator[str, None]) -> list[str]:
    """Drain an async generator into a list."""
    chunks: list[str] = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_question_over_500_chars_then_raises_422() -> None:
    """A question longer than 500 characters is rejected before any DB call."""
    long_question = "x" * 501

    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await explain_subtopic_question(
            subtopic_id=_SUBTOPIC_ID,
            student_id=_STUDENT_ID,
            school_id=_SCHOOL_ID,
            question=long_question,
            db=db,
        )

    assert exc_info.value.status_code == 422
    # DB should never be touched for an over-length question
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_subtopic_not_found_then_raises_404() -> None:
    """A subtopic UUID that does not exist in the DB raises a 404."""
    db = AsyncMock(spec=AsyncSession)

    # First execute (subtopic join) returns no row
    subtopic_result = MagicMock()
    subtopic_result.one_or_none.return_value = None
    db.execute.return_value = subtopic_result

    with pytest.raises(HTTPException) as exc_info:
        await explain_subtopic_question(
            subtopic_id=_SUBTOPIC_ID,
            student_id=_STUDENT_ID,
            school_id=_SCHOOL_ID,
            question="What is a linear equation?",
            db=db,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_valid_question_then_yields_sse_chunks() -> None:
    """A valid question streams SSE-formatted chunks ending with [DONE]."""
    db = AsyncMock(spec=AsyncSession)

    # First execute: subtopic row
    subtopic_result = MagicMock()
    subtopic_result.one_or_none.return_value = _mock_subtopic_row()

    # Second execute: learning profile
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = _mock_profile()

    db.execute.side_effect = [subtopic_result, profile_result]

    # Mock litellm streaming: two delta chunks
    async def _fake_stream() -> AsyncGenerator:
        for text in ["Hello", " world"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            yield chunk

    with patch("app.services.concept_guide_service.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = _fake_stream()

        gen = await explain_subtopic_question(
            subtopic_id=_SUBTOPIC_ID,
            student_id=_STUDENT_ID,
            school_id=_SCHOOL_ID,
            question="What is a linear equation?",
            db=db,
        )

        chunks = await _collect(gen)

    assert any("Hello" in c for c in chunks), "Expected 'Hello' chunk in SSE output"
    assert chunks[-1] == "data: [DONE]\n\n", "Last chunk must be the SSE done sentinel"
    # Confirm SSE format
    for chunk in chunks[:-1]:
        assert chunk.startswith("data: "), f"Chunk not SSE-formatted: {chunk!r}"


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_student_has_no_profile_then_uses_defaults() -> None:
    """When no learning profile exists the service falls back to defaults without raising."""
    db = AsyncMock(spec=AsyncSession)

    subtopic_result = MagicMock()
    subtopic_result.one_or_none.return_value = _mock_subtopic_row()

    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = None  # no profile

    db.execute.side_effect = [subtopic_result, profile_result]

    async def _fake_stream() -> AsyncGenerator:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "Sure!"
        yield chunk

    with patch("app.services.concept_guide_service.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = _fake_stream()

        gen = await explain_subtopic_question(
            subtopic_id=_SUBTOPIC_ID,
            student_id=_STUDENT_ID,
            school_id=_SCHOOL_ID,
            question="Explain please.",
            db=db,
        )

        chunks = await _collect(gen)

    # Must complete without error and emit the done sentinel
    assert "data: [DONE]\n\n" in chunks
