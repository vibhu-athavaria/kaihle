#!/usr/bin/env python3
"""Quiz Quality Review Harness — M3-1-T3.

Review harness for human quiz review before deployment.
Reads previously generated quiz JSON files from data/quiz_review/ and
outputs a summary report for teacher/curriculum-admin review.

Usage:
    python scripts/quiz_quality_review.py --input data/quiz_review/pending/
    python scripts/quiz_quality_review.py --list
    python scripts/quiz_quality_review.py --approve <quiz_id>
    python scripts/quiz_quality_review.py --reject <quiz_id> --reason "..."

Exit codes:
    0 - success
    1 - validation error
    2 - file not found
    3 - no pending quizzes
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

QUIZ_REVIEW_DIR = Path(__file__).parent.parent / "data" / "quiz_review"
PENDING_DIR = QUIZ_REVIEW_DIR / "pending"
APPROVED_DIR = QUIZ_REVIEW_DIR / "approved"
REJECTED_DIR = QUIZ_REVIEW_DIR / "rejected"


def ensure_dirs() -> None:
    """Ensure all review subdirectories exist."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)


def list_pending() -> list[Path]:
    """Return sorted list of pending quiz JSON files."""
    if not PENDING_DIR.exists():
        return []
    return sorted(PENDING_DIR.glob("*.json"))


def load_quiz(path: Path) -> dict:
    """Load quiz JSON from file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_quiz(quiz: dict, dest: Path) -> None:
    """Save quiz JSON to destination path."""
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(quiz, f, indent=2, ensure_ascii=False)
        f.write("\n")


def print_quiz_summary(quiz: dict, quiz_id: str) -> None:
    """Print a human-readable summary of a quiz."""
    subtopic_id = quiz.get("subtopic_id", "unknown")
    generated_at = quiz.get("generated_at", "unknown")
    interests = quiz.get("interests_used", [])
    questions = quiz.get("questions", [])

    print(f"\n{'=' * 60}")
    print(f"Quiz ID:        {quiz_id}")
    print(f"Subtopic ID:    {subtopic_id}")
    print(f"Generated:     {generated_at}")
    print(f"Interests used: {', '.join(interests) if interests else '(none)'}")
    print(f"Questions:      {len(questions)}")
    print("-" * 60)

    for i, q in enumerate(questions, 1):
        print(f"\n  Q{i}. {q.get('question_text', 'N/A')}")
        print(f"      Type: {q.get('type', 'N/A')}")
        for opt in q.get("options", []):
            marker = "✓" if opt.get("key") == q.get("correct_answer") else " "
            print(f"      [{marker}] {opt.get('key')}. {opt.get('text', 'N/A')}")
        print(f"      Explanation: {q.get('explanation', 'N/A')}")


def cmd_list() -> None:
    """List all pending quizzes awaiting review."""
    ensure_dirs()
    pending = list_pending()
    if not pending:
        print("No pending quizzes for review.")
        sys.exit(3)

    print(f"\nPending quizzes ({len(pending)}):")
    print("-" * 60)
    for path in pending:
        quiz = load_quiz(path)
        questions = quiz.get("questions", [])
        generated = quiz.get("generated_at", "unknown")
        print(f"  {path.stem}")
        print(f"    Questions: {len(questions)} | Generated: {generated}")
    print(f"\nTotal: {len(pending)} pending")
    print("\nReview a quiz: python scripts/quiz_quality_review.py <quiz_id>")
    print("Then use --approve or --reject to action it.")


def cmd_review(quiz_id: str) -> None:
    """Display a specific quiz for human review."""
    ensure_dirs()
    pending = list_pending()
    matching = [p for p in pending if p.stem == quiz_id]
    if not matching:
        print(f"Quiz '{quiz_id}' not found in pending queue.")
        print("Run --list to see available quizzes.")
        sys.exit(2)

    path = matching[0]
    quiz = load_quiz(path)
    print_quiz_summary(quiz, quiz_id)


def cmd_approve(quiz_id: str) -> None:
    """Move a quiz from pending to approved."""
    ensure_dirs()
    pending = list_pending()
    matching = [p for p in pending if p.stem == quiz_id]
    if not matching:
        print(f"Quiz '{quiz_id}' not found in pending queue.")
        sys.exit(2)

    source = matching[0]
    quiz = load_quiz(source)
    quiz["review_status"] = "approved"
    quiz["reviewed_at"] = datetime.utcnow().isoformat()

    dest = APPROVED_DIR / f"{quiz_id}.json"
    save_quiz(quiz, dest)
    source.unlink()  # Remove from pending

    print(f"✓ Quiz '{quiz_id}' approved and moved to approved/")


def cmd_reject(quiz_id: str, reason: str) -> None:
    """Move a quiz from pending to rejected with reason."""
    ensure_dirs()
    pending = list_pending()
    matching = [p for p in pending if p.stem == quiz_id]
    if not matching:
        print(f"Quiz '{quiz_id}' not found in pending queue.")
        sys.exit(2)

    source = matching[0]
    quiz = load_quiz(source)
    quiz["review_status"] = "rejected"
    quiz["reviewed_at"] = datetime.utcnow().isoformat()
    quiz["rejection_reason"] = reason

    dest = REJECTED_DIR / f"{quiz_id}.json"
    save_quiz(quiz, dest)
    source.unlink()  # Remove from pending

    print(f"✗ Quiz '{quiz_id}' rejected and moved to rejected/")
    print(f"  Reason: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quiz Quality Review Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_argument("--list", action="store_true", help="List all pending quizzes")

    sub.add_argument("quiz_id", nargs="?", help="Quiz ID to review")
    sub.add_argument("--approve", action="store_true", help="Approve the specified quiz")
    sub.add_argument("--reject", action="store_true", help="Reject the specified quiz")
    sub.add_argument("--reason", default="", help="Rejection reason (required with --reject)")

    args = parser.parse_args()

    if args.command == "list" or (hasattr(args, "list") and args.list):
        cmd_list()
    elif args.quiz_id and args.approve:
        cmd_approve(args.quiz_id)
    elif args.quiz_id and args.reject:
        if not args.reason:
            print("Error: --reason is required when rejecting a quiz.")
            sys.exit(1)
        cmd_reject(args.quiz_id, args.reason)
    elif args.quiz_id:
        cmd_review(args.quiz_id)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
