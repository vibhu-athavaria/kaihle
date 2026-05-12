import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import School
from app.models.user import User
from app.schemas.class_enrollment import ClassCreate
from app.services.class_service import ClassService


@pytest.mark.asyncio
async def test_create_class_returns_class_with_relationships_loaded(
    db_session: AsyncSession,
    test_school: School,
    test_teacher: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    """Test that created class has subject, grade, and teacher relationships loaded."""
    # Arrange
    service = ClassService(db_session)
    data = ClassCreate(
        name="Test Class",
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=test_teacher.id,
        academic_year="2026-2027",
    )

    # Act
    created_class = await service.create_class(test_school.id, data)

    # Assert: Accessing these should NOT trigger lazy load (and thus not raise MissingGreenlet)
    assert created_class.subject is not None
    assert created_class.subject.id == test_subject.id
    assert created_class.subject.name == test_subject.name

    assert created_class.grade is not None
    assert created_class.grade.id == test_grade.id
    assert created_class.grade.name == test_grade.name

    assert created_class.teacher is not None
    assert created_class.teacher.id == test_teacher.id
    assert created_class.teacher.first_name == test_teacher.first_name
    assert created_class.teacher.last_name == test_teacher.last_name
