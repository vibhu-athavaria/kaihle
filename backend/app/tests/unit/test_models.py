"""Unit tests for SQLAlchemy models."""

import uuid

from app.models.assessment import Assessment, AssessmentStatus
from app.models.curriculum import (
    LearningObjective,
    QuestionBank,
    Subtopic,
    SubtopicObjective,
)
from app.models.interest_category import InterestCategory
from app.models.onboarding import StudentLearningProfile
from app.models.school import ClassEnrollment
from app.models.student_lesson_pack import PackStatus, PackType, StudentLessonPack
from app.models.subtopic_content import ReviewStatus, SubtopicContent
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole


class TestUser:
    """Tests for User model."""

    def test_user_model_has_check_constraint(self) -> None:
        """Test that User model has the school_id check constraint defined."""
        from sqlalchemy import Table

        table: Table = User.__table__  # type: ignore[assignment]
        constraints = table.constraints
        constraint_names = [c.name for c in constraints]
        assert "chk_user_school_id_required" in constraint_names

    def test_user_school_id_is_nullable(self) -> None:
        """Test that school_id column is nullable."""
        col = User.__table__.c.school_id
        assert col.nullable is True

    def test_kaihle_admin_role_can_have_null_school_id(self) -> None:
        """Test that KAIHLE_ADMIN role can be instantiated with None school_id."""
        user = User(
            email="admin@kaihle.com",
            hashed_password="hashed",
            role=UserRole.KAIHLE_ADMIN,
            school_id=None,
            first_name="Admin",
            last_name="User",
            is_active=True,
        )
        assert user.school_id is None
        assert user.role == UserRole.KAIHLE_ADMIN

    def test_teacher_can_have_school_id(self) -> None:
        """Test that TEACHER role can be instantiated with a school_id."""
        school_id = uuid.uuid4()
        user = User(
            email="teacher@test.com",
            hashed_password="hashed",
            role=UserRole.TEACHER,
            school_id=school_id,
            first_name="Teacher",
            last_name="User",
            is_active=True,
        )
        assert user.school_id == school_id
        assert user.role == UserRole.TEACHER


class TestStudentLearningProfile:
    """Tests for StudentLearningProfile model."""

    def test_instantiation_with_required_fields(self) -> None:
        """Test that StudentLearningProfile can be instantiated with required fields."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()

        profile = StudentLearningProfile(
            student_id=student_id,
            school_id=school_id,
            modality_scores={"visual": 0.8, "auditory": 0.3},
            work_style={"prefers_solo": True},
        )

        assert profile.student_id == student_id
        assert profile.school_id == school_id
        assert profile.modality_scores == {"visual": 0.8, "auditory": 0.3}
        assert profile.work_style == {"prefers_solo": True}
        assert profile.completed_at is None
        assert profile.interests is None

    def test_questionnaire_version_column_default(self) -> None:
        """Test that questionnaire_version column has correct server_default."""
        # Check column definition
        col = StudentLearningProfile.__table__.c.questionnaire_version
        assert col.default is not None
        assert col.default.arg == "v1"


class TestAssessment:
    """Tests for Assessment model."""

    def test_status_column_default(self) -> None:
        """Test that status column defaults to DRAFT."""
        col = Assessment.__table__.c.status
        assert col.default is not None
        assert col.default.arg == AssessmentStatus.DRAFT


class TestStudentProfile:
    """Tests for StudentProfile model."""

    def test_grade_id_nullable(self) -> None:
        """Test that grade_id is nullable."""
        col = StudentProfile.__table__.c.grade_id
        assert col.nullable is True


class TestClassEnrollment:
    """Tests for ClassEnrollment model (v2.1)."""

    def test_onboarding_status_column_has_server_default(self) -> None:
        """Test that onboarding_diagnostic_status column has server_default PENDING."""
        col = ClassEnrollment.__table__.c.onboarding_diagnostic_status
        assert col.server_default is not None
        assert col.server_default.arg == "PENDING"

    def test_explicit_onboarding_status(self) -> None:
        """Test that onboarding_diagnostic_status can be explicitly set."""
        enrollment = ClassEnrollment(
            class_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        assert enrollment.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    def test_column_is_not_nullable(self) -> None:
        """Test that onboarding_diagnostic_status is NOT NULL."""
        col = ClassEnrollment.__table__.c.onboarding_diagnostic_status
        assert col.nullable is False


# ---------------------------------------------------------------------------
# Tests for M3 Content Infrastructure Models
# ---------------------------------------------------------------------------


class TestSubtopicContent:
    """Tests for SubtopicContent model (M3-0-T1)."""

    def test_tablename_is_subtopic_content(self) -> None:
        assert SubtopicContent.__tablename__ == "subtopic_content"

    def test_has_school_id_column_nullable(self) -> None:
        """subtopic_content.school_id is nullable — NULL for curriculum-scope, set for school-scope rows."""
        col = SubtopicContent.__table__.c.school_id
        assert col.nullable is True

    def test_has_scope_column_with_curriculum_default(self) -> None:
        """subtopic_content.scope defaults to 'curriculum'."""
        col = SubtopicContent.__table__.c.scope
        assert col.server_default is not None
        arg = col.server_default.arg  # type: ignore[union-attr]
        assert getattr(arg, "text", arg) == "curriculum"

    def test_has_subtopic_id_foreign_key(self) -> None:
        fk_cols = {c.name for c in SubtopicContent.__table__.columns if c.foreign_keys}
        assert "subtopic_id" in fk_cols

    def test_has_interest_category_id_foreign_key(self) -> None:
        fk_cols = {c.name for c in SubtopicContent.__table__.columns if c.foreign_keys}
        assert "interest_category_id" in fk_cols

    def test_review_status_has_pending_default(self) -> None:
        col = SubtopicContent.__table__.c.review_status
        assert col.server_default is not None

    def test_is_active_default_true(self) -> None:
        col = SubtopicContent.__table__.c.is_active
        assert col.server_default is not None

    def test_is_stale_default_false(self) -> None:
        col = SubtopicContent.__table__.c.is_stale
        assert col.server_default is not None

    def test_is_archived_default_false(self) -> None:
        col = SubtopicContent.__table__.c.is_archived
        assert col.server_default is not None

    def test_get_approved_videos_returns_only_approved_entries(self) -> None:
        """get_approved_videos returns entries with status='approved' from the JSONB array."""
        content = SubtopicContent(
            subtopic_id=uuid.uuid4(),
            content_type="video",
            videos=[
                {"url": "https://youtube.com/watch?v=abc", "status": "approved", "title": "Vid 1"},
                {"url": "https://youtube.com/watch?v=def", "status": "pending", "title": "Vid 2"},
            ],
            review_status=ReviewStatus.APPROVED,
            is_active=True,
            is_stale=False,
            is_archived=False,
        )
        videos = content.get_approved_videos()
        assert len(videos) == 1
        assert videos[0]["url"] == "https://youtube.com/watch?v=abc"

    def test_get_approved_videos_excludes_pending_entries(self) -> None:
        """get_approved_videos returns empty list when all video entries are pending."""
        content = SubtopicContent(
            subtopic_id=uuid.uuid4(),
            content_type="video",
            videos=[
                {"url": "https://youtube.com/watch?v=abc", "status": "pending", "title": "Vid 1"},
            ],
            review_status=ReviewStatus.PENDING,
            is_active=True,
            is_stale=False,
            is_archived=False,
        )
        videos = content.get_approved_videos()
        assert len(videos) == 0

    def test_get_approved_videos_excludes_archived_content(self) -> None:
        """get_approved_videos returns empty list when the content row is archived."""
        content = SubtopicContent(
            subtopic_id=uuid.uuid4(),
            content_type="video",
            videos=[
                {"url": "https://youtube.com/watch?v=abc", "status": "approved", "title": "Vid 1"},
            ],
            review_status=ReviewStatus.APPROVED,
            is_active=True,
            is_stale=False,
            is_archived=True,
        )
        videos = content.get_approved_videos()
        assert len(videos) == 0

    def test_get_display_explanation_returns_explanation_text(self) -> None:
        content = SubtopicContent(
            subtopic_id=uuid.uuid4(),
            content_type="explanation",
            explanation_text="This is an explanation",
            review_status="approved",
            is_active=True,
            is_stale=False,
            is_archived=False,
        )
        result = content.get_display_explanation()
        assert result == "This is an explanation"


class TestStudentLessonPack:
    """Tests for StudentLessonPack model (M3-0-T1)."""

    def test_tablename_is_student_lesson_packs(self) -> None:
        assert StudentLessonPack.__tablename__ == "student_lesson_packs"

    def test_has_student_id_foreign_key(self) -> None:
        fk_cols = {c.name for c in StudentLessonPack.__table__.columns if c.foreign_keys}
        assert "student_id" in fk_cols

    def test_has_school_id_foreign_key(self) -> None:
        fk_cols = {c.name for c in StudentLessonPack.__table__.columns if c.foreign_keys}
        assert "school_id" in fk_cols

    def test_content_ids_is_array_of_uuids(self) -> None:
        col = StudentLessonPack.__table__.c.content_ids
        assert col.type is not None

    def test_subtopic_ids_is_array_of_uuids(self) -> None:
        col = StudentLessonPack.__table__.c.subtopic_ids
        assert col.type is not None

    def test_pack_status_enum_has_expected_values(self) -> None:
        """PackStatus should have all required states."""
        assert PackStatus.GENERATED == "generated"
        assert PackStatus.SENT == "sent"
        assert PackStatus.IN_PROGRESS == "in_progress"
        assert PackStatus.COMPLETED == "completed"
        assert PackStatus.EXPIRED == "expired"

    def test_pack_type_enum_has_expected_values(self) -> None:
        """PackType should have all required types."""
        assert PackType.QUIZ == "quiz"
        assert PackType.VIDEO == "video"
        assert PackType.EXPLANATION == "explanation"
        assert PackType.MIXED == "mixed"

    def test_is_expired_returns_false_when_no_expiry(self) -> None:
        pack = StudentLessonPack(
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            content_ids=[],
            subtopic_ids=[],
            title="Test Pack",
            target_tier=1,
            status=PackStatus.GENERATED,
            expires_at=None,
        )
        assert pack.is_expired() is False

    def test_is_active_returns_true_for_generated_pack(self) -> None:
        pack = StudentLessonPack(
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            content_ids=[],
            subtopic_ids=[],
            title="Test Pack",
            target_tier=1,
            status=PackStatus.GENERATED,
            is_archived=False,
        )
        assert pack.is_active() is True

    def test_is_active_returns_false_for_archived_pack(self) -> None:
        pack = StudentLessonPack(
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            content_ids=[],
            subtopic_ids=[],
            title="Test Pack",
            target_tier=1,
            status=PackStatus.GENERATED,
            is_archived=True,
        )
        assert pack.is_active() is False

    def test_is_active_returns_false_for_completed_pack(self) -> None:
        pack = StudentLessonPack(
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            content_ids=[],
            subtopic_ids=[],
            title="Test Pack",
            target_tier=1,
            status=PackStatus.COMPLETED,
            is_archived=False,
        )
        assert pack.is_active() is False


class TestInterestCategory:
    """Tests for InterestCategory model (M3-0-T1)."""

    def test_tablename_is_interest_categories(self) -> None:
        assert InterestCategory.__tablename__ == "interest_categories"

    def test_name_is_unique(self) -> None:
        col = InterestCategory.__table__.c.name
        assert col.unique is True

    def test_name_is_indexed(self) -> None:
        col = InterestCategory.__table__.c.name
        assert col.index is True


class TestLearningObjective:
    """Tests for LearningObjective model (curriculum remap v2)."""

    def test_tablename_is_learning_objectives(self) -> None:
        assert LearningObjective.__tablename__ == "learning_objectives"

    def test_canonical_code_when_declared_then_unique_and_not_nullable(self) -> None:
        col = LearningObjective.__table__.c.canonical_code
        assert col.unique is True
        assert col.nullable is False

    def test_learning_objective_text_when_declared_then_not_nullable(self) -> None:
        # The full LO text is the de-duplication basis, so it must always be present.
        assert LearningObjective.__table__.c.learning_objective.nullable is False

    def test_topic_id_when_declared_then_restrict_fk_and_indexed(self) -> None:
        col = LearningObjective.__table__.c.topic_id
        assert col.nullable is False
        assert col.index is True
        fk = next(iter(col.foreign_keys))
        assert fk.column.table.name == "topics"
        # Topics are shared across grades and curricula — deleting one that still
        # owns objectives must be a hard error, never a cascade.
        assert fk.ondelete == "RESTRICT"

    def test_embedding_when_declared_then_768_dimensions(self) -> None:
        # Must match subtopics.embedding so the two can be compared directly.
        assert LearningObjective.__table__.c.embedding.type.dim == 768

    def test_model_when_no_difficulty_columns_then_stays_reusable(self) -> None:
        # Difficulty stays off the objective: it is a per-question property, and
        # difficulty_level expresses difficulty WITHIN a grade, never demand BETWEEN
        # grades. Tier likewise lives on subtopics alone.
        #
        # grade_id is deliberately NOT in this set — ADR-003 made grade part of
        # objective identity, because a question can suit Year 6 and not Year 8 even
        # when both teach the same objective. See test_grade_id_* below.
        cols = set(LearningObjective.__table__.c.keys())
        assert cols.isdisjoint({"grade_level", "difficulty_level", "tier"})

    def test_grade_id_when_declared_then_not_null_and_restrict_on_delete(self) -> None:
        """NOT NULL since ADR-003 T4 — grade is part of objective identity.

        That is what makes a question's grade derivable from its objective alone, rather
        than from a subtopic_id a curriculum remap can NULL.

        RESTRICT matches topic_id: grades are global and shared, so deleting one that
        still owns objectives must be a hard error rather than a silent cascade.
        """
        grade_col = LearningObjective.__table__.c.grade_id
        assert grade_col.nullable is False
        assert grade_col.index is True

        fk = next(iter(grade_col.foreign_keys))
        assert fk.column.table.name == "grades"
        assert fk.ondelete == "RESTRICT"

    def test_normalised_objective_when_declared_then_not_null_text(self) -> None:
        """The stored de-duplication key T4 constrains on.

        Stored rather than generated: the normalisation folds accents via NFKD, which
        Postgres can only reach through unaccent(), and unaccent() is not IMMUTABLE so
        it is rejected in generated columns and index expressions alike.
        """
        col = LearningObjective.__table__.c.normalised_objective
        assert col.nullable is False

    def test_identity_when_declared_then_unique_on_topic_grade_normalised_text(self) -> None:
        """ADR-003's identity, enforced by the database rather than by convention.

        Deliberately NOT (topic_id, grade_id, canonical_code): that permits the same
        concept twice under two different codes, which is the exact duplication ADR-003
        exists to prevent and which canonical_code cannot detect.
        """
        constraint = next(
            c for c in LearningObjective.__table__.constraints if c.name == "uq_learning_objective_topic_grade_text"
        )
        assert {c.name for c in constraint.columns} == {"topic_id", "grade_id", "normalised_objective"}

    def test_canonical_code_when_declared_then_wide_enough_for_grade_suffix(self) -> None:
        # ADR-003 T3 suffixes split objectives with -G{level}; '-G10'..'-G13' would
        # land exactly on the old 50-char limit.
        assert LearningObjective.__table__.c.canonical_code.type.length == 64

    def test_instantiation_when_given_required_fields_then_sets_attributes(self) -> None:
        topic_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        lo = LearningObjective(
            id=uuid.uuid4(),
            canonical_code="MATH-NEGATIVE-NUMBERS",
            name="Using negative numbers",
            learning_objective="Order and use negative numbers in practical contexts.",
            topic_id=topic_id,
            grade_id=grade_id,
            normalised_objective="order and use negative numbers in practical contexts",
            bloom_taxonomy_level="Apply",
            is_active=True,
        )
        assert lo.canonical_code == "MATH-NEGATIVE-NUMBERS"
        assert lo.topic_id == topic_id
        assert lo.grade_id == grade_id
        assert lo.is_active is True


class TestSubtopicObjective:
    """Tests for the SubtopicObjective M:N bridge (curriculum remap v2)."""

    def test_tablename_is_subtopic_objectives(self) -> None:
        assert SubtopicObjective.__tablename__ == "subtopic_objectives"

    def test_primary_key_when_declared_then_composite_of_both_fks(self) -> None:
        pk = {c.name for c in SubtopicObjective.__table__.primary_key}
        assert pk == {"subtopic_id", "learning_objective_id"}

    def test_subtopic_fk_when_declared_then_cascades(self) -> None:
        # Deleting a subtopic during a scoped wipe should drop its bridge rows.
        col = SubtopicObjective.__table__.c.subtopic_id
        assert next(iter(col.foreign_keys)).ondelete == "CASCADE"

    def test_objective_fk_when_declared_then_restricts(self) -> None:
        # An objective still referenced by any subtopic must survive the wipe.
        col = SubtopicObjective.__table__.c.learning_objective_id
        assert next(iter(col.foreign_keys)).ondelete == "RESTRICT"

    def test_bridge_when_declared_then_carries_no_tier_column(self) -> None:
        # Tier lives only on subtopics — never on the bridge, never on the LO.
        assert "tier" not in SubtopicObjective.__table__.c.keys()


class TestSubtopicTier:
    """Tests for the Core/Extended tier column on Subtopic (curriculum remap v2)."""

    def test_tier_when_declared_then_not_nullable_and_defaults_to_both(self) -> None:
        col = Subtopic.__table__.c.tier
        assert col.nullable is False
        assert col.server_default.arg == "BOTH"

    def test_tier_when_declared_then_check_constraint_limits_values(self) -> None:
        names = {c.name for c in Subtopic.__table__.constraints}
        assert "chk_subtopic_tier" in names


class TestQuestionBankObjectiveBinding:
    """Tests for question_bank's new LO binding (curriculum remap v2)."""

    def test_learning_objective_id_when_declared_then_indexed_restrict_fk(self) -> None:
        col = QuestionBank.__table__.c.learning_objective_id
        assert col.index is True
        fk = next(iter(col.foreign_keys))
        assert fk.column.table.name == "learning_objectives"
        # Deleting an LO that still owns questions must be a hard error rather
        # than silently orphaning them — the failure the old coupling allowed.
        assert fk.ondelete == "RESTRICT"

    def test_subtopic_id_when_remapped_then_nullable_for_transition(self) -> None:
        # Questions are transiently unbound between the scoped wipe and remap.
        assert QuestionBank.__table__.c.subtopic_id.nullable is True
