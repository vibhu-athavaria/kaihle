#!/usr/bin/env python3
"""
One-off script to flatten cambridge_v1.json into a CSV for curriculum review.

Run from repo root:
    python backend/scripts/extract_curriculum_for_review.py

Output:
    backend/data/curriculum/curriculum_review.csv

This file is gitignored. Share with Vibhu / Vidhya for M1-2-T3b review.
"""

import csv
import json
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).parent.parent
    json_path = repo_root / "data" / "curriculum" / "cambridge_v1.json"
    csv_path = repo_root / "data" / "curriculum" / "curriculum_review.csv"

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for entry in data["curriculum_tree"]:
        curriculum = entry["curriculum_code"]
        subject = entry["subject_code"]
        grade = entry["grade_level"]
        for topic in entry["topics"]:
            topic_name = topic["name"]
            seq = topic.get("sequence_order", "")
            for subtopic in topic["subtopics"]:
                diff = subtopic.get("difficulty_level", "")
                prereqs = subtopic.get("prerequisites", [])
                rows.append(
                    {
                        "curriculum": curriculum,
                        "subject": subject,
                        "grade": grade,
                        "topic_sequence": seq,
                        "topic_name": topic_name,
                        "subtopic_code": subtopic.get("canonical_code", ""),
                        "subtopic_name": subtopic["name"],
                        "learning_objective": subtopic.get("learning_objective", ""),
                        "difficulty_min": diff,
                        "difficulty_max": "",  # JSON has no range — only scalar difficulty_level
                        "prerequisite_codes": "; ".join(prereqs),
                        "review_ok": "",  # reviewer fills: Y / N
                        "correction_needed": "",  # reviewer fills free text
                    }
                )

    if not rows:
        print("ERROR: No rows extracted — check curriculum_tree structure in JSON")
        raise SystemExit(1)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Exported {len(rows)} subtopics to {csv_path}")
    print("  Share this file with Vibhu/Vidhya for M1-2-T3b curriculum review.")


if __name__ == "__main__":
    main()
