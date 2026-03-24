# M1-2-T3 — Curriculum Content Review (Vidhya Sign-Off)
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-2 — Curriculum Graph & RAG Ingestion
**Task ID:** M1-2-T3
**Depends on:** M1-2-T1 task file must exist (does not need to have run)
**Must complete before:** M1-2-T1 (seeding script runs), M1-1-T1 (question import)
**Blocks:** M1-2-T1, M1-3-T3 (assessment wizard uses topic names from seeded data)
**Estimated effort:** 4–6 hours (Vidhya review) + 1–2 hours (Kramer corrections)
**Lead persona:** Vidhya (curriculum accuracy) with Kramer (data corrections)

> **Why this task is a blocker before M1-2-T1:**
> `cambridge_v1.json` contains 193 subtopics with Cambridge objective codes (e.g. `7Ma.01`).
> These codes appear directly in AI-generated lesson plans. If a code is wrong, every lesson
> plan generated for the pilot school will reference invalid curriculum. Cambridge-certified
> teachers will notice this immediately and it will undermine trust in the platform.
> The cost of reviewing the JSON now is 4–6 hours. The cost of noticing the error after
> the pilot school is live is incalculable.

---

## Vidhya — Curriculum Accuracy Review

### What to review

The file `backend/data/curriculum/cambridge_v1.json` contains the following structure:

```
curricula (2 entries)
  cambridge_lower (Grades 6–8: MATH, SCI, ENG)
  igcse (Grades 9–10: MATH, BIO, CHEM, PHY, ENG, ENGL)

For each curriculum × subject × grade:
  topics[] (approx 4–6 per subject/grade)
    subtopics[] (approx 3–5 per topic)
      canonical_code: e.g. "MATH-NUM-G6-01"
      learning_objective: free text aligned to Cambridge descriptor
      difficulty_range: [min, max] on 1.0–5.0 scale
      prerequisites: list of canonical codes that must be understood first
```

**Total to review:** 21 curriculum entries (see table in M1-2-T1) × avg 4 topics × avg 3 subtopics = approximately 252 subtopic entries, though the actual JSON has exactly 193.

### Review checklist per subtopic

For each subtopic, Vidhya should verify:

1. **Name accuracy** — does the subtopic name match Cambridge's published syllabus terminology?
   - Cambridge Lower Secondary: check against [Cambridge Lower Secondary Mathematics (0862), Science (0893), English (0851) syllabuses]
   - Cambridge IGCSE: check against [0580 Mathematics, 0610 Biology, 0620 Chemistry, 0625 Physics, 0500 English, 0475 Literature syllabuses]

2. **Learning objective alignment** — does the `learning_objective` field use language consistent with the Cambridge learning outcome descriptors for that stage/year?
   - Lower Secondary uses "Stages" (Stage 7, 8, 9 for Grades 6, 7, 8)
   - IGCSE uses learning outcomes from the relevant syllabus section

3. **Objective code format** — Cambridge codes follow the pattern:
   - Lower Secondary Mathematics: `7Ma.01`, `8Ma.02` (Stage-Subject.Number)
   - Lower Secondary Science: `7Sb.01` (biology strand), `7Sc.01` (chemistry), `7Sp.01` (physics)
   - IGCSE: uses section/chapter numbers, not the same code format
   - Current JSON uses `MATH-NUM-G6-01` format (internal canonical codes, NOT Cambridge codes)
   - **IMPORTANT:** These are Kaihle's own internal codes, not Cambridge's published codes.
     Verify that the lesson plan prompt template (`lesson_plan_system.jinja2`) references
     these codes correctly and that teachers will not be confused by them appearing in plans.

4. **Prerequisite logic** — does the prerequisite chain make educational sense?
   - E.g., "Quadratic Equations" should require "Expanding Brackets" and "Factoring"
   - E.g., "Photosynthesis" should require "Cell Structure"
   - Check a representative sample (at least 20%) for logical prerequisite chains

5. **Difficulty range** — does the `difficulty_range: [min, max]` reflect the relative difficulty of the subtopic within its subject and grade?
   - Grade 6 Maths subtopics should generally be difficulty 1.0–2.5
   - Grade 10 IGCSE Physics should be difficulty 3.0–5.0
   - Spot-check for outliers

### Priority areas (most likely to have issues)

Based on Vidhya's domain expertise, these areas warrant the most careful review:

**Mathematics:**
- Algebra and Functions naming conventions differ between Lower Secondary and IGCSE
- Trigonometry — verify it only appears in Grade 9–10 (IGCSE), not Grade 6–8
- Statistics — Cambridge uses "Statistics and Probability" as a combined strand

**Integrated Science (Lower Secondary):**
- The file uses SCI for all three strands (biology, chemistry, physics) at Grades 6–8
- Verify the topic names are correct for a combined/integrated science course
- Cambridge Lower Secondary Science has separate strands — check these are unified correctly

**English Language vs English Literature:**
- ENG = English Language (both curricula)
- ENGL = English Literature (IGCSE only)
- These are entirely different syllabus documents — verify no mixing of content

**IGCSE Biology/Chemistry/Physics:**
- These are the most complex syllabuses with many detailed learning objectives
- Verify topic groupings match Cambridge's own unit/chapter structure

### Output format

Vidhya should produce one of the following:
1. **No corrections needed** — sign-off comment in `cambridge_v1.json` `_meta.vidhya_review` field
2. **Minor corrections** — list of specific changes with justification
3. **Structural issues** — flag to Vibhu before M1 begins (rare, but possible)

---

## Kramer — Implementation Deliverables

### Step 1: Extract review-friendly CSV

Before Vidhya begins, run this script to extract the JSON into a CSV format that is
easier to review than raw JSON:

```python
# backend/scripts/extract_curriculum_for_review.py
"""
One-off script to produce a flat CSV from cambridge_v1.json for Vidhya's review.
Output: backend/data/curriculum/curriculum_review.csv
"""
import json
import csv
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
            rows.append({
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
            })

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Exported {len(rows)} subtopics to {csv_path}")
```

Run with: `python backend/scripts/extract_curriculum_for_review.py`

This produces `backend/data/curriculum/curriculum_review.csv` — share with Vidhya.

### Step 2: Apply corrections

After Vidhya's review, apply any corrections to `cambridge_v1.json`. Common types:

**Name correction:**
```json
// Before
{ "name": "Force and Motion" }
// After (using Cambridge's exact published term)
{ "name": "Forces and Their Effects" }
```

**Learning objective correction:**
```json
// Before
{ "learning_objective": "Understand gravity" }
// After (aligned to Cambridge descriptor)
{ "learning_objective": "Describe gravity as a non-contact force that attracts masses and understand the difference between mass and weight." }
```

**Prerequisite correction:**
```json
// Before: no prerequisites listed for Quadratic Equations
{ "prerequisites": [] }
// After: correctly requires prior subtopics
{ "prerequisites": ["MATH-ALG-G8-03", "MATH-ALG-G8-04"] }
```

### Step 3: Update `_meta` in JSON

After corrections are applied, update the `_meta` section of `cambridge_v1.json`:

```json
"_meta": {
  "version": "1.1",
  "authored_by": "Vidhya (curriculum content) + Kramer (structure validation)",
  "reviewed_by": "Vidhya",
  "review_date": "2026-03-[date]",
  "review_status": "approved",
  "corrections_applied": [N],
  "date": "2026-03",
  ...
}
```

### Step 4: Update M1-2-T1 acceptance criteria

After this review, add a note to `M1-2-T1_curriculum_graph_seeding.md`:
```
> Note: cambridge_v1.json was reviewed and approved by Vidhya on [date] per M1-2-T3.
> Do NOT modify cambridge_v1.json without a new Vidhya review.
```

---

## Files to Create / Modify

```
backend/scripts/extract_curriculum_for_review.py  ← CREATE (one-off review tool)
backend/data/curriculum/curriculum_review.csv     ← CREATE (output of review script, gitignored)
backend/data/curriculum/cambridge_v1.json         ← MODIFY: apply corrections + update _meta
docs/tasks/M1/M1-2-T1_curriculum_graph_seeding.md ← MODIFY: add sign-off note
```

Add `curriculum_review.csv` to `.gitignore` — it is a working document, not a source file.

---

## Acceptance Criteria

- [ ] `extract_curriculum_for_review.py` runs and produces a readable CSV with all 193 subtopics
- [ ] Vidhya has reviewed the CSV and provided written sign-off or a corrections list
- [ ] All corrections are applied to `cambridge_v1.json`
- [ ] `cambridge_v1.json` `_meta.review_status` = `"approved"`
- [ ] `cambridge_v1.json` `_meta.reviewed_by` = `"Vidhya"`
- [ ] `cambridge_v1.json` remains valid JSON: `python -m json.tool cambridge_v1.json > /dev/null` exits 0
- [ ] At minimum, Vidhya has verified: (a) all topic names are Cambridge-accurate, (b) ENGL content is Literature not Language, (c) SCI topics are appropriate for integrated science, (d) prerequisite chains are logical for at least 20% of subtopics sampled
- [ ] M1-2-T1 task file updated with sign-off note
- [ ] No M1 coding begins until this task is marked complete

---

## Do NOT Touch

- The JSON structure (keys, nesting, types) — only content values change
- `M0-10-T2b` curriculum routes — already built and tested against empty tables; content changes don't affect route code
- Any existing test files
