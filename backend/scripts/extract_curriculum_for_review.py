"""
One-off script to produce a flat CSV from cambridge_v1.json for Vidhya's review.
Output: backend/data/curriculum/curriculum_review.csv
"""

import csv
import json
from pathlib import Path

json_path = Path(__file__).parent.parent / "data/curriculum/cambridge_v1.json"
csv_path = Path(__file__).parent.parent / "data/curriculum/curriculum_review.csv"

with open(json_path) as f:
    data = json.load(f)

rows = []
for entry in data["curriculum_tree"]:
    curriculum = entry["curriculum_code"]
    subject = entry["subject_code"]
    grade = entry["grade_level"]
    for topic in entry["topics"]:
        for subtopic in topic["subtopics"]:
            rows.append(
                {
                    "curriculum": curriculum,
                    "subject": subject,
                    "grade": grade,
                    "topic_name": topic["name"],
                    "subtopic_canonical_code": subtopic["canonical_code"],
                    "subtopic_name": subtopic["name"],
                    "learning_objective": subtopic["learning_objective"],
                    "difficulty_min": subtopic.get("difficulty_range", [None, None])[0],
                    "difficulty_max": subtopic.get("difficulty_range", [None, None])[1],
                    "prerequisite_count": len(subtopic.get("prerequisites", [])),
                }
            )

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Exported {len(rows)} subtopics to {csv_path}")
