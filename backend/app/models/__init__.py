"""SQLAlchemy ORM models for Kaihle."""

from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    StudentAttempt,
    StudentResponse,
)
from app.models.base import Base
from app.models.billing import (
    SchoolSubscription,
    SubscriptionInvoice,
    SubscriptionPlan,
    TrialExtension,
)
from app.models.class_topic import ClassTopic
from app.models.curriculum import (
    Curriculum,
    CurriculumChunk,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicPrerequisite,
    Topic,
)
from app.models.gap import GapState
from app.models.interest_category import InterestCategory
from app.models.lesson_plan import LessonPlan
from app.models.mini_course import MiniCourseStudentOverride, SubtopicContentFeedback, SubtopicCourseProgress
from app.models.onboarding import StudentLearningProfile
from app.models.parent import ParentReportSnapshot
from app.models.school import Class, ClassEnrollment, School, SchoolCurriculum
from app.models.student_lesson_pack import StudentLessonPack
from app.models.study_plan import StudyPlan, StudyPlanQuiz, StudyPlanResource
from app.models.subtopic_content import SubtopicContent
from app.models.user import (
    AuthToken,
    ParentStudent,
    StudentProfile,
    TeacherProfile,
    User,
)

__all__ = [
    "Base",
    "Curriculum",
    "Subject",
    "Grade",
    "Topic",
    "CurriculumSubject",
    "CurriculumTopic",
    "Subtopic",
    "StudentLessonPack",
    "SubtopicContent",
    "SubtopicPrerequisite",
    "CurriculumChunk",
    "QuestionBank",
    "School",
    "SchoolCurriculum",
    "Class",
    "ClassEnrollment",
    "ClassTopic",
    "User",
    "StudentProfile",
    "TeacherProfile",
    "ParentStudent",
    "AuthToken",
    "StudentLearningProfile",
    "Assessment",
    "AssessmentSelectedQuestion",
    "StudentAttempt",
    "StudentResponse",
    "GapState",
    "InterestCategory",
    "StudyPlan",
    "StudyPlanResource",
    "StudyPlanQuiz",
    "LessonPlan",
    "ParentReportSnapshot",
    "SubscriptionPlan",
    "SchoolSubscription",
    "SubscriptionInvoice",
    "TrialExtension",
    "SubtopicCourseProgress",
    "SubtopicContentFeedback",
    "MiniCourseStudentOverride",
]
