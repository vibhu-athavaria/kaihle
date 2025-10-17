"""
Script to import question bank data from a JSON file
Usage:
    python import_question_bank.py science_questions_800.json
"""

import sys
import os
import json
import traceback

# Add project root to Python path (same as your seeder)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.assessment import QuestionBank  # ensure you have this model
from sqlalchemy.exc import IntegrityError
from psycopg2.extras import Json


def import_question_bank(json_file: str):
    db: Session = SessionLocal()

    try:
        print(f"🌱 Importing questions from {json_file}...")

        with open(json_file, "r") as f:
            data = json.load(f)

        count = 0

        if(type(data) is not list):
            print("❌ JSON root should be an array of questions.")
            return

        seen_questions = set()

        for item in data:
            # Print full question object to verify and get user confirmation
            print("\033[2J\033[H", end="")

            q_key = (
                item.get("question_text"),
                item.get("subject"),
                item.get("grade_level")
            )

            if q_key in seen_questions:
                print("⚠️ Duplicate in same file. Skipping.")
                continue

            print(f"Importing Question: {json.dumps(item, indent=2)}")
            # get user confirmation before adding
            confirm = input("Add this question to the database? (y/n): ")
            if confirm.lower() != 'y':
                print("Skipping this question.")
                continue

            # Map JSON fields → database columns
            question = QuestionBank(
                subject=item.get("subject"),
                subtopic=item.get("subtopic"),
                grade_level=item.get("grade_level"),
                prerequisites=item.get("prerequisites", []),
                # description=item.get("explanation", ""),
                learning_objectives=item.get("learning_objectives", []),
                question_text=item.get("question_text"),
                question_type=item.get("question_type"),
                options=item.get("options", []),
                correct_answer=item.get("correct_answer"),
                difficulty_level=item.get("difficulty_level")
            )

            # before adding check if question already exists to avoid duplicates
            existing = db.query(QuestionBank).filter_by(
                question_text=question.question_text,
                subject=question.subject,
                grade_level=question.grade_level
            ).first()
            if existing:
                print("⚠️ Question already exists in the database. Skipping.")
                continue
            db.add(question)
            seen_questions.add(q_key)
            count += 1

            # Commit in batches for performance
            if count % 100 == 0:
                db.commit()
                print(f"✅ Imported {count} questions so far...")

            db.commit()
            print(f"🎉 Successfully imported {count} questions into question_bank!")

    except FileNotFoundError:
        print(f"❌ File not found: {json_file}")
    except IntegrityError as e:
        db.rollback()
        print(f"⚠️ Database integrity error: {e}")
    except Exception as e:
        db.rollback()
        print(f"❌ Error importing data: {e}")
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python import_question_bank.py <path_to_json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    import_question_bank(json_file)
