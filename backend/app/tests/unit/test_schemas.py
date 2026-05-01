"""Smoke tests — verify every schema can be instantiated with valid data."""

import uuid
from datetime import date, datetime

import pytest

from app.models.user import UserRole
from app.schemas.analytics import (
    AtRiskStudent,
    ClassBreakdown,
    OnboardingFunnel,
    PlatformStats,
    SchoolAnalytics,
)
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentQuestion,
    AssessmentQuestionWithAnswer,
    AssessmentResponse,
    QuestionOption,
)
from app.schemas.attempts import (
    AnswerSubmitRequest,
    AttemptResponse,
    AttemptResultResponse,
    AttemptSubmitRequest,
)
from app.schemas.common import ErrorDetail, Page
from app.schemas.curriculum import (
    CurriculumResponse,
    GradeResponse,
    SubjectResponse,
    SubtopicResponse,
    TopicResponse,
)
from app.schemas.gap_map import (
    ClassGapMap,
    ClassSummary,
    GapMapNode,
    StudentGapMap,
    StudentGapScore,
    StudentSubtopicScore,
)
from app.schemas.lesson_plans import (
    LessonPlanEditRequest,
    LessonPlanResponse,
    LessonPlanStatusRequest,
)
from app.schemas.parent import (
    ChildSummary,
    ParentGapMap,
    SubjectGapSummary,
    TopicStatus,
    WeeklyReport,
)
from app.schemas.study_plans import (
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanAssignRequest,
    StudyPlanAssignResponse,
    StudyPlanQuizQuestion,
    StudyPlanResource,
    StudyPlanResponse,
)
from app.schemas.user import UserDirectCreate


class TestSchemaInstantiation:
    """Smoke tests for all Pydantic schemas."""

    def test_page_schema(self):
        p = Page[dict](data=[], total=0, page=1, page_size=20)
        assert p.total == 0
        assert p.page == 1
        assert p.page_size == 20

    def test_error_detail_schema(self):
        e = ErrorDetail(error_code="TEST_ERROR", message="Test message")
        assert e.error_code == "TEST_ERROR"
        assert e.message == "Test message"
        assert e.details == {}

    def test_class_gap_map_empty_nodes(self):
        g = ClassGapMap(
            class_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            generated_at=datetime.utcnow(),
            nodes=[],
        )
        assert g.nodes == []

    def test_student_gap_score_with_none_mastery(self):
        s = StudentGapScore(
            student_id=uuid.uuid4(),
            student_name="Test Student",
            mastery_score=None,
            last_assessed_at=None,
        )
        assert s.mastery_score is None
        assert s.last_assessed_at is None

    def test_gap_map_node(self):
        n = GapMapNode(
            subtopic_id=uuid.uuid4(),
            subtopic_name="Test Subtopic",
            topic_id=uuid.uuid4(),
            topic_name="Test Topic",
            class_average=None,
            student_count=0,
            student_scores=[],
        )
        assert n.class_average is None
        assert n.student_count == 0

    def test_student_subtopic_score(self):
        s = StudentSubtopicScore(
            subtopic_id=uuid.uuid4(),
            subtopic_name="Test Subtopic",
            topic_id=uuid.uuid4(),
            topic_name="Test Topic",
            mastery_score=0.75,
            last_assessed_at=datetime.utcnow(),
        )
        assert s.mastery_score == 0.75

    def test_student_gap_map(self):
        g = StudentGapMap(
            student_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            generated_at=datetime.utcnow(),
            scores=[],
        )
        assert g.scores == []

    def test_class_summary(self):
        c = ClassSummary(
            class_id=uuid.uuid4(),
            avg_mastery=None,
            student_count=25,
            assessed_student_count=0,
            last_updated_at=None,
        )
        assert c.avg_mastery is None
        assert c.student_count == 25
        assert c.assessed_student_count == 0

    def test_question_option(self):
        q = QuestionOption(key="a", text="Option A")
        assert q.key == "a"
        assert q.text == "Option A"

    def test_assessment_question(self):
        q = AssessmentQuestion(
            question_id=uuid.uuid4(),
            question_text="What is 2+2?",
            question_type="MCQ",
            options=[
                QuestionOption(key="a", text="3"),
                QuestionOption(key="b", text="4"),
            ],
        )
        assert q.question_text == "What is 2+2?"
        assert len(q.options) == 2
        # Student-facing question should NOT have correct_answer
        assert not hasattr(q, "correct_answer_key")

    def test_assessment_question_with_answer(self):
        q = AssessmentQuestionWithAnswer(
            question_id=uuid.uuid4(),
            question_text="What is 2+2?",
            question_type="MCQ",
            options=[QuestionOption(key="a", text="3")],
            correct_answer_key="b",
            explanation="2+2=4",
        )
        assert q.correct_answer_key == "b"
        assert q.explanation == "2+2=4"

    def test_assessment_response(self):
        a = AssessmentResponse(
            id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            title="Test Assessment",
            assessment_type="DIAGNOSTIC",
            is_system_generated=True,
            status="DRAFT",
            topic_ids=[uuid.uuid4()],
            question_count=20,
            created_at=datetime.utcnow(),
            published_at=None,
            deadline=None,
        )
        assert a.status == "DRAFT"
        assert a.question_count == 20

    def test_assessment_create_request(self):
        r = AssessmentCreateRequest(
            title="New Assessment",
            topic_ids=[uuid.uuid4()],
        )
        assert r.title == "New Assessment"
        assert r.question_count == 20  # default

    def test_attempt_response_not_started(self):
        a = AttemptResponse(
            id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            status="NOT_STARTED",
            started_at=None,
            submitted_at=None,
            score=None,
            questions=[],
        )
        assert a.status == "NOT_STARTED"
        assert a.questions == []

    def test_attempt_response_in_progress(self):
        a = AttemptResponse(
            id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            status="IN_PROGRESS",
            started_at=datetime.utcnow(),
            submitted_at=None,
            score=None,
            questions=[],
        )
        assert a.status == "IN_PROGRESS"
        assert a.started_at is not None

    def test_answer_submit_request(self):
        a = AnswerSubmitRequest(
            question_id=uuid.uuid4(),
            selected_key="b",
        )
        assert a.selected_key == "b"

    def test_attempt_submit_request(self):
        a = AttemptSubmitRequest(
            answers=[
                AnswerSubmitRequest(question_id=uuid.uuid4(), selected_key="a"),
                AnswerSubmitRequest(question_id=uuid.uuid4(), selected_key="b"),
            ],
        )
        assert len(a.answers) == 2

    def test_attempt_result_response(self):
        r = AttemptResultResponse(
            attempt_id=uuid.uuid4(),
            score=0.75,
            total_questions=20,
            correct_count=15,
            time_taken_seconds=600,
            submitted_at=datetime.utcnow(),
        )
        assert r.score == 0.75
        assert r.correct_count == 15

    def test_lesson_plan_response(self) -> None:
        lesson_plan = LessonPlanResponse(
            id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            week_start=date.today(),
            status="GENERATED",
            generated_plan={"starter": "intro"},
            teacher_edits=None,
            created_at=datetime.utcnow(),
        )
        assert lesson_plan.status == "GENERATED"
        assert lesson_plan.generated_plan is not None

    def test_lesson_plan_edit_request_partial(self):
        e = LessonPlanEditRequest(starter_10min="New starter activity")
        assert e.starter_10min == "New starter activity"
        assert e.group_a_activity is None

    def test_lesson_plan_status_request(self):
        s = LessonPlanStatusRequest(status="USED")
        assert s.status == "USED"

    def test_study_plan_resource(self):
        r = StudyPlanResource(
            resource_id=uuid.uuid4(),
            title="Video on Fractions",
            resource_type="VIDEO",
            url="https://youtube.com/watch?v=123",
            source="YOUTUBE",
            duration_minutes=10,
            is_watched=False,
        )
        assert r.resource_type == "VIDEO"
        assert not r.is_watched

    def test_study_plan_quiz_question(self):
        q = StudyPlanQuizQuestion(
            question_index=0,
            question_text="What is 1/2 + 1/4?",
            options=[{"key": "a", "text": "1/2"}, {"key": "b", "text": "3/4"}],
        )
        assert q.question_index == 0
        # Should NOT have correct_answer
        assert not hasattr(q, "correct_answer")

    def test_study_plan_response(self):
        s = StudyPlanResponse(
            id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            subtopic_id=uuid.uuid4(),
            subtopic_name="Fractions",
            status="ACTIVE",
            resources=[],
            quiz_questions=[],
            quiz_score=None,
            created_at=datetime.utcnow(),
        )
        assert s.status == "ACTIVE"
        assert s.quiz_score is None

    def test_study_plan_assign_request_with_students(self) -> None:
        r = StudyPlanAssignRequest(
            subtopic_id=uuid.uuid4(),
            student_ids=[uuid.uuid4(), uuid.uuid4()],
        )
        assert r.student_ids is not None
        assert len(r.student_ids) == 2

    def test_study_plan_assign_request_all_students(self):
        r = StudyPlanAssignRequest(subtopic_id=uuid.uuid4(), student_ids=None)
        assert r.student_ids is None

    def test_study_plan_assign_response(self):
        r = StudyPlanAssignResponse(
            status="generating",
            plans=[
                {"plan_id": uuid.uuid4(), "student_id": uuid.uuid4(), "status": "GENERATING"},
            ],
        )
        assert r.status == "generating"
        assert len(r.plans) == 1

    def test_quiz_submit_request(self):
        r = QuizSubmitRequest(
            responses=[
                {"question_index": 0, "answer": "a"},
                {"question_index": 1, "answer": "b"},
            ],
        )
        assert len(r.responses) == 2

    def test_quiz_submit_response(self):
        r = QuizSubmitResponse(
            score=0.8,
            correct_count=8,
            total_questions=10,
            plan_status="COMPLETED",
        )
        assert r.score == 0.8

    def test_child_summary(self):
        c = ChildSummary(
            student_id=uuid.uuid4(),
            first_name="Emma",
            last_name="Smith",
            grade_name="Grade 9",
            school_name="Test School",
            subjects=["Mathematics", "Science"],
        )
        assert c.first_name == "Emma"
        assert len(c.subjects) == 2

    def test_topic_status(self):
        t = TopicStatus(topic_name="Algebra", status="Strong", status_label="green")
        assert t.status == "Strong"
        assert t.status_label == "green"

    def test_subject_gap_summary(self):
        s = SubjectGapSummary(
            subject_name="Mathematics",
            topics=[
                TopicStatus(topic_name="Algebra", status="Strong", status_label="green"),
                TopicStatus(topic_name="Geometry", status="Developing", status_label="amber"),
            ],
        )
        assert len(s.topics) == 2

    def test_parent_gap_map_has_no_mastery_score_field(self):
        g = ParentGapMap(student_name="Emma", grade_name="Grade 9", subjects=[])
        assert not hasattr(g, "mastery_score")
        assert g.student_name == "Emma"

    def test_weekly_report(self):
        w = WeeklyReport(
            report_id=uuid.uuid4(),
            week_start=date.today(),
            subject_name="Mathematics",
            narrative="Emma showed great progress this week.",
            highlights=["Completed all homework", "Participated in class"],
            created_at=datetime.utcnow(),
        )
        assert len(w.highlights) == 2

    def test_class_breakdown(self):
        c = ClassBreakdown(
            class_id=uuid.uuid4(),
            class_name="9A",
            subject_name="Mathematics",
            grade_name="Grade 9",
            teacher_name="Mr. Smith",
            student_count=30,
            avg_mastery=0.72,
            assessments_completed=5,
        )
        assert c.avg_mastery == 0.72

    def test_school_analytics_zero_values(self):
        s = SchoolAnalytics(
            school_id=uuid.uuid4(),
            generated_at=datetime.utcnow(),
            total_students=0,
            active_students=0,
            assessments_completed=0,
            study_plans_active=0,
            onboarding_funnel=OnboardingFunnel(
                invited=0,
                password_set=0,
                profile_complete=0,
                diagnostic_done=0,
            ),
            classes=[],
            at_risk_students=[],
        )
        assert s.total_students == 0
        assert s.classes == []

    def test_school_analytics_with_classes(self):
        s = SchoolAnalytics(
            school_id=uuid.uuid4(),
            generated_at=datetime.utcnow(),
            total_students=100,
            active_students=95,
            assessments_completed=50,
            study_plans_active=30,
            onboarding_funnel=OnboardingFunnel(
                invited=100,
                password_set=95,
                profile_complete=90,
                diagnostic_done=80,
            ),
            classes=[
                ClassBreakdown(
                    class_id=uuid.uuid4(),
                    class_name="9A",
                    subject_name="Mathematics",
                    grade_name="Grade 9",
                    teacher_name="Mr. Smith",
                    student_count=30,
                    avg_mastery=0.72,
                    assessments_completed=5,
                ),
            ],
            at_risk_students=[
                AtRiskStudent(
                    student_id=uuid.uuid4(),
                    first_name="Bob",
                    last_name="Jones",
                    worst_mastery=0.25,
                    needs_work_class_count=2,
                ),
            ],
        )
        assert len(s.classes) == 1
        assert s.active_students == 95

    def test_platform_stats(self):
        p = PlatformStats(
            total_schools=5,
            total_active_students=500,
            total_teachers=50,
            assessments_completed_last_7_days=200,
            generated_at=datetime.utcnow(),
        )
        assert p.total_schools == 5
        assert p.total_active_students == 500

    def test_grade_response(self):
        cid = uuid.uuid4()
        g = GradeResponse(
            id=uuid.uuid4(),
            name="Grade 9",
            level=9,
            is_active=True,
            curriculum_ids=[cid],
        )
        assert g.level == 9
        assert g.is_active is True
        assert cid in g.curriculum_ids

    def test_subject_response(self):
        s = SubjectResponse(
            id=uuid.uuid4(),
            name="Mathematics",
            code="MATH",
        )
        assert s.code == "MATH"

    def test_topic_response(self):
        t = TopicResponse(
            id=uuid.uuid4(),
            name="Algebra",
            subject_id=uuid.uuid4(),
            grade_id=uuid.uuid4(),
            order=1,
        )
        assert t.order == 1

    def test_subtopic_response(self):
        s = SubtopicResponse(
            id=uuid.uuid4(),
            name="Linear Equations",
            topic_id=uuid.uuid4(),
            order=1,
        )
        assert s.name == "Linear Equations"

    def test_curriculum_response(self):
        c = CurriculumResponse(
            id=uuid.uuid4(),
            name="Cambridge IGCSE",
            code="igcse",
            is_active=True,
        )
        assert c.is_active


def test_user_direct_create_student_valid():
    data = UserDirectCreate(
        first_name="Aisha",
        last_name="Al-Rashid",
        email="aisha@school.edu",
        password="Secure123!",
        role=UserRole.STUDENT,
        age=13,
        grade_id=uuid.uuid4(),
    )
    assert data.role == UserRole.STUDENT
    assert data.age == 13


def test_user_direct_create_student_missing_grade_raises():
    with pytest.raises(Exception):
        UserDirectCreate(
            first_name="A",
            last_name="B",
            email="a@b.com",
            password="Secure123!",
            role=UserRole.STUDENT,
            age=13,
            # grade_id omitted - should raise for STUDENT
        )


def test_user_direct_create_teacher_valid():
    data = UserDirectCreate(
        first_name="Rachel",
        last_name="Morgan",
        email="r@school.edu",
        password="Secure123!",
        role=UserRole.TEACHER,
    )
    assert data.class_ids is None  # optional


def test_user_direct_create_parent_valid():
    data = UserDirectCreate(
        first_name="James",
        last_name="Smith",
        email="j@gmail.com",
        password="Secure123!",
        role=UserRole.PARENT,
        student_ids=[uuid.uuid4()],
    )
    assert len(data.student_ids) == 1
