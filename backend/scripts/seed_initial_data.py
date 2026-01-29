"""
Script to seed the database with initial data
Run this after creating and running migrations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.crud.user import create_user
from app.crud.study_plan import create_lesson
from app.crud.progress import create_badge
from app.schemas.user import UserCreate
from app.schemas.study_plan import StudyPlanCourseCreate
from app.schemas.progress import BadgeCreate

def seed_data():
    db = SessionLocal()

    try:
        print("🌱 Seeding initial data...")

        # Create admin user
        admin_data = UserCreate(
            email="admin@school.com",
            username="admin",
            password="admin123",
            full_name="System Administrator",
            role="admin"
        )
        admin_user = create_user(db, admin_data)
        print(f"✅ Created admin user: {admin_user.email}")

        # Create sample parent user
        parent_data = UserCreate(
            email="parent@example.com",
            username="parent1",
            password="parent123",
            full_name="John Parent",
            role="parent"
        )
        parent_user = create_user(db, parent_data)
        print(f"✅ Created parent user: {parent_user.email}")

        # Create sample lessons
        lessons_data = [
            {
                "title": "Introduction to Mathematics",
                "description": "Basic mathematical concepts and operations",
                "content": "Learn about numbers, addition, subtraction, and basic problem solving.",
                "difficulty_level": "beginner",
                "subject": "mathematics",
                "points_value": 10
            },
            {
                "title": "Reading Comprehension Basics",
                "description": "Fundamental reading skills and comprehension strategies",
                "content": "Develop reading skills through engaging stories and exercises.",
                "difficulty_level": "beginner",
                "subject": "english",
                "points_value": 15
            },
            {
                "title": "Science Exploration",
                "description": "Introduction to scientific thinking and observation",
                "content": "Explore the world around us through simple experiments and observations.",
                "difficulty_level": "beginner",
                "subject": "science",
                "points_value": 20
            },
            {
                "title": "Advanced Algebra",
                "description": "Complex algebraic equations and problem solving",
                "content": "Master advanced algebraic concepts including quadratic equations and functions.",
                "difficulty_level": "advanced",
                "subject": "mathematics",
                "points_value": 30
            }
        ]

        for lesson_data in lessons_data:
            lesson = create_lesson(db, LessonCreate(**lesson_data))
            print(f"✅ Created lesson: {lesson.title}")

        # Create sample badges
        badges_data = [
            {
                "name": "First Steps",
                "description": "Complete your first lesson",
                "icon": "🎯",
                "points_required": 10
            },
            {
                "name": "Quick Learner",
                "description": "Earn 100 points",
                "icon": "⚡",
                "points_required": 100
            },
            {
                "name": "Dedicated Student",
                "description": "Earn 500 points",
                "icon": "📚",
                "points_required": 500
            },
            {
                "name": "Math Master",
                "description": "Complete 10 math lessons",
                "icon": "🔢",
                "points_required": 200
            },
            {
                "name": "Reading Champion",
                "description": "Complete 10 reading lessons",
                "icon": "📖",
                "points_required": 200
            }
        ]

        for badge_data in badges_data:
            badge = create_badge(db, BadgeCreate(**badge_data))
            print(f"✅ Created badge: {badge.name}")

        print("🎉 Initial data seeding completed successfully!")

    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
