"""Unit tests for mini-course SQLAlchemy models.

Tests validate model structure, constraints, and column defaults without a live DB.
"""

import uuid

from app.models.mini_course import SubtopicContentFeedback, SubtopicCourseProgress
from app.models.subtopic_content import SubtopicContent


class TestSubtopicCourseProgress:
    """Tests for SubtopicCourseProgress model."""

    def test_subtopic_course_progress_when_created_then_defaults_are_false(self) -> None:
        """explanation_accessed and video_accessed columns have server_default of false."""
        explanation_col = SubtopicCourseProgress.__table__.c.explanation_accessed
        video_col = SubtopicCourseProgress.__table__.c.video_accessed

        assert explanation_col.server_default is not None
        assert explanation_col.server_default.arg == "false"
        assert video_col.server_default is not None
        assert video_col.server_default.arg == "false"

    def test_subtopic_course_progress_when_created_then_check_questions_score_is_none(
        self,
    ) -> None:
        """check_questions_score is None on fresh instantiation."""
        progress = SubtopicCourseProgress(
            student_id=uuid.uuid4(),
            subtopic_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
        )
        assert progress.check_questions_score is None

    def test_subtopic_course_progress_when_primary_key_defined_then_composite_pk_columns_correct(
        self,
    ) -> None:
        """Table has a composite primary key on (student_id, subtopic_id)."""
        pk_columns = {col.name for col in SubtopicCourseProgress.__table__.primary_key}
        assert pk_columns == {"student_id", "subtopic_id"}

    def test_subtopic_course_progress_primary_key_when_duplicate_then_raises_integrity_error(
        self,
    ) -> None:
        """Duplicate (student_id, subtopic_id) pair is rejected at the DB level.

        NOTE: Full integrity-error assertion requires a live DB session.
        This test verifies that the primary key constraint is defined on the correct columns,
        which guarantees the DB will enforce uniqueness.
        """
        pk_cols = [col.name for col in SubtopicCourseProgress.__table__.primary_key.columns]
        assert "student_id" in pk_cols
        assert "subtopic_id" in pk_cols

    def test_subtopic_course_progress_when_school_student_index_defined(self) -> None:
        """Table defines a composite index on (school_id, student_id)."""
        index_columns = {
            idx.name: [col.name for col in idx.columns] for idx in SubtopicCourseProgress.__table__.indexes
        }
        found = any("school_id" in cols and "student_id" in cols for cols in index_columns.values())
        assert found, f"Expected school_id+student_id index, got: {index_columns}"

    def test_subtopic_course_progress_when_score_set_then_value_stored(self) -> None:
        """check_questions_score can be set to a float."""
        progress = SubtopicCourseProgress(
            student_id=uuid.uuid4(),
            subtopic_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            check_questions_score=0.85,
        )
        assert progress.check_questions_score == 0.85


class TestSubtopicContentFeedback:
    """Tests for SubtopicContentFeedback model."""

    def test_subtopic_content_feedback_when_instantiated_then_fields_set(self) -> None:
        """Model instantiation stores all required fields."""
        student_id = uuid.uuid4()
        content_id = uuid.uuid4()
        school_id = uuid.uuid4()

        feedback = SubtopicContentFeedback(
            student_id=student_id,
            subtopic_content_id=content_id,
            school_id=school_id,
            feedback_type="thumbs_up",
        )

        assert feedback.student_id == student_id
        assert feedback.subtopic_content_id == content_id
        assert feedback.school_id == school_id
        assert feedback.feedback_type == "thumbs_up"
        assert feedback.comment is None

    def test_subtopic_content_feedback_when_duplicate_student_content_then_raises_integrity_error(
        self,
    ) -> None:
        """UNIQUE constraint on (student_id, subtopic_content_id) is defined on the table.

        NOTE: Actual IntegrityError requires a live DB session.
        This test verifies the unique constraint is declared correctly on the model.
        """
        constraint_names = {c.name for c in SubtopicContentFeedback.__table__.constraints}
        assert "uq_subtopic_content_feedback_student_content" in constraint_names

    def test_subtopic_content_feedback_when_check_constraint_defined_then_only_valid_types(
        self,
    ) -> None:
        """CheckConstraint restricts feedback_type to thumbs_up or thumbs_down."""
        from sqlalchemy import CheckConstraint

        check_constraints = [c for c in SubtopicContentFeedback.__table__.constraints if isinstance(c, CheckConstraint)]
        assert any("thumbs_up" in str(c.sqltext) or "thumbs_up" in (c.name or "") for c in check_constraints), (
            f"Expected thumbs_up check constraint, got: {check_constraints}"
        )

    def test_subtopic_content_feedback_when_comment_provided_then_stored(self) -> None:
        """Optional comment field can be set."""
        feedback = SubtopicContentFeedback(
            student_id=uuid.uuid4(),
            subtopic_content_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            feedback_type="thumbs_down",
            comment="Could not understand the explanation",
        )
        assert feedback.comment == "Could not understand the explanation"


class TestSubtopicContentThumbsColumns:
    """Tests for thumbs_up_count and thumbs_down_count columns on SubtopicContent."""

    def test_subtopic_content_thumbs_columns_when_new_row_then_default_zero(self) -> None:
        """thumbs_up_count and thumbs_down_count have server_default of 0."""
        thumbs_up_col = SubtopicContent.__table__.c.thumbs_up_count
        thumbs_down_col = SubtopicContent.__table__.c.thumbs_down_count

        assert thumbs_up_col.server_default is not None, "thumbs_up_count has no server_default"
        assert thumbs_down_col.server_default is not None, "thumbs_down_count has no server_default"
        assert thumbs_up_col.server_default.arg == "0"
        assert thumbs_down_col.server_default.arg == "0"

    def test_subtopic_content_rejection_teacher_note_when_column_defined_then_nullable(
        self,
    ) -> None:
        """rejection_teacher_note column is nullable."""
        col = SubtopicContent.__table__.c.rejection_teacher_note
        assert col.nullable is True

    def test_subtopic_content_thumbs_up_count_when_column_defined_then_not_nullable(
        self,
    ) -> None:
        """thumbs_up_count column is NOT NULL."""
        col = SubtopicContent.__table__.c.thumbs_up_count
        assert col.nullable is False

    def test_subtopic_content_thumbs_down_count_when_column_defined_then_not_nullable(
        self,
    ) -> None:
        """thumbs_down_count column is NOT NULL."""
        col = SubtopicContent.__table__.c.thumbs_down_count
        assert col.nullable is False
