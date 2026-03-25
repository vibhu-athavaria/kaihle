# M1-2-T3a — Generate Curriculum Review CSV
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-2 — Curriculum Graph & RAG Ingestion
**Task ID:** M1-2-T3a
**Executor:** Coding agent
**Depends on:** `backend/data/curriculum/cambridge_v1.json` exists (committed in M0)
**Must complete before:** M1-2-T3b (Vibhu + Vidhya need this CSV to do their review)
**Blocks:** M1-2-T3b → M1-2-T1
**Estimated effort:** 30 minutes

---

## What This Task Does

Creates a one-off script that flattens `cambridge_v1.json` into a spreadsheet-friendly
CSV so that Vibhu and Vidhya can review the 193 subtopics without reading raw JSON.

The CSV is gitignored — it is a working document, not a source file.

---

## File to Create

```
backend/scripts/extract_curriculum_for_review.py
```

Add `backend/data/curriculum/curriculum_review.csv` to `.gitignore`.

---

## Implementation

```python
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
                diff = subtopic.get("difficulty_range", [None, None])
                prereqs = subtopic.get("prerequisites", [])
                rows.append({
                    "curriculum": curriculum,
                    "subject": subject,
                    "grade": grade,
                    "topic_sequence": seq,
                    "topic_name": topic_name,
                    "subtopic_code": subtopic.get("canonical_code", ""),
                    "subtopic_name": subtopic["name"],
                    "learning_objective": subtopic.get("learning_objective", ""),
                    "difficulty_min": diff[0] if diff[0] is not None else "",
                    "difficulty_max": diff[1] if diff[1] is not None else "",
                    "prerequisite_codes": "; ".join(prereqs),
                    "review_ok": "",        # reviewer fills: Y / N
                    "correction_needed": "", # reviewer fills free text
                })

    if not rows:
        print("ERROR: No rows extracted — check curriculum_tree structure in JSON")
        raise SystemExit(1)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Exported {len(rows)} subtopics to {csv_path}")
    print(f"  Share this file with Vibhu/Vidhya for M1-2-T3b curriculum review.")


if __name__ == "__main__":
    main()
```

---

## .gitignore addition

In `backend/.gitignore` (or root `.gitignore`), add:

```
# Curriculum review working document — not a source file
backend/data/curriculum/curriculum_review.csv
```

---

## Acceptance Criteria

- [ ] Script runs without errors: `python backend/scripts/extract_curriculum_for_review.py`
- [ ] Output CSV contains exactly 193 rows (one per subtopic)
- [ ] CSV columns: `curriculum`, `subject`, `grade`, `topic_sequence`, `topic_name`, `subtopic_code`, `subtopic_name`, `learning_objective`, `difficulty_min`, `difficulty_max`, `prerequisite_codes`, `review_ok`, `correction_needed`
- [ ] `review_ok` and `correction_needed` columns are empty — they are filled by the human reviewer in M1-2-T3b
- [ ] `curriculum_review.csv` is present in `.gitignore`
- [ ] Script exits with a clear error message if JSON structure is unexpected (not a silent empty file)

---

## Do NOT Touch

- `cambridge_v1.json` — read-only input, not modified by this script
- Any existing backend routes, models, or tests
