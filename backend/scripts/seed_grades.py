"""
Script to seed the grades table with initial grade levels
Run this after creating and running migrations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.crud.grade import create_grade, get_grades
from app.schemas.grade import GradeCreate


def seed_grades():
    db = SessionLocal()

    try:
        print("🌱 Seeding grades data...")

        # Check if grades already exist
        existing_grades = get_grades(db)
        if existing_grades:
            print("✅ Grades already exist, skipping seeding.")
            return

        # Define grades to seed
        grades_data = [
            {"name": "5th Grade", "level": 5, "description": "Grade 5"},
            {"name": "6th Grade", "level": 6, "description": "Grade 6"},
            {"name": "7th Grade", "level": 7, "description": "Grade 7"},
            {"name": "8th Grade", "level": 8, "description": "Grade 8"},
            {"name": "9th Grade", "level": 9, "description": "Grade 9"},
            {"name": "10th Grade", "level": 10, "description": "Grade 10"},
            {"name": "11th Grade", "level": 11, "description": "Grade 11"},
            {"name": "12th Grade", "level": 12, "description": "Grade 12"},
        ]

        for grade_data in grades_data:
            grade = create_grade(db, GradeCreate(**grade_data))
            print(f"✅ Created grade: {grade.name} (Level {grade.level})")

        print("🎉 Grades seeding completed successfully!")

    except Exception as e:
        print(f"❌ Error seeding grades: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_grades()