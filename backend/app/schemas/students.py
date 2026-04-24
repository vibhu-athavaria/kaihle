"""Pydantic schemas for student-related API responses."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnrolledClassInfo(BaseModel):
    """Info about a single enrolled class with its subject."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    class_id: UUID = Field(..., alias="classId")
    class_name: str = Field(..., alias="className")
    subject_id: UUID = Field(..., alias="subjectId")
    subject_name: str = Field(..., alias="subjectName")
    grade_name: str = Field(..., alias="gradeName")


class StudentInfoResponse(BaseModel):
    """Response schema for GET /students/{student_id}/info.

    Note: streak_days is not yet implemented and will always be null.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    email: str = Field(..., alias="email")
    grade_name: str = Field(..., alias="gradeName")
    curriculum_name: str = Field(..., alias="curriculumName")
    class_id: UUID | None = Field(None, alias="classId")
    streak_days: int | None = Field(None, alias="streakDays")
    is_enrolled: bool = Field(..., alias="isEnrolled")
    enrolled_classes: list[EnrolledClassInfo] = Field(default_factory=list, alias="enrolledClasses")


class StudentClassResponse(BaseModel):
    """Response schema for GET /students/me/classes."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(..., alias="id")
    name: str = Field(..., alias="name")
    subject_id: UUID = Field(..., alias="subjectId")
    subject_name: str = Field(..., alias="subjectName")
    grade_name: str = Field(..., alias="gradeName")
    teacher_name: str = Field(..., alias="teacherName")
    curriculum_id: UUID = Field(..., alias="curriculumId")
    academic_year: str = Field(..., alias="academicYear")
    is_active: bool = Field(..., alias="isActive")
    onboarding_diagnostic_status: str = Field(..., alias="onboardingDiagnosticStatus")
    diagnostic_attempt_id: UUID | None = Field(None, alias="diagnosticAttemptId")


class ConceptGuideRequest(BaseModel):
    """Request body for POST /students/me/concept-guide."""

    subtopic_id: UUID = Field(..., description="UUID of the subtopic to explain")
    question: str | None = Field(None, max_length=500, description="Optional specific question from the student")


class CheckQuestion(BaseModel):
    """MCQ check question returned alongside a concept explanation."""

    question: str
    options: list[str]
    correct: str


class ConceptGuideResponse(BaseModel):
    """Response for POST /students/me/concept-guide."""

    explanation: str
    subtopic_name: str
    check_question: CheckQuestion | None = None


class McqAnswerRequest(BaseModel):
    """Request body for POST /students/me/concept-guide/answer."""

    subtopic_name: str
    question: str
    options: list[str]
    correct: str
    student_answer: str = Field(..., max_length=10)


class McqAnswerResponse(BaseModel):
    """Response for POST /students/me/concept-guide/answer."""

    is_correct: bool
    response: str
