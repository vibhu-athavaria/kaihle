# Mastery Threshold Rationale
**Document type:** Design decision record
**Author:** Vidhya (Curriculum Lead) + Kramer (Technical implementation)
**Date:** March 2026
**Status:** Authoritative — do not change thresholds without updating this document

---

## The Decision

Kaihle uses two mastery score boundaries applied globally across all subjects, grade levels,
curricula, and roles:

| Score range | Label | Meaning |
|---|---|---|
| `score > 0.7` | **Strong** | Student demonstrates confident understanding |
| `0.4 ≤ score ≤ 0.7` | **Developing** | Student shows partial understanding; targeted support needed |
| `score < 0.4` | **Needs Work** | Student has foundational gaps; immediate intervention needed |
| `null` | **Not assessed** | No assessment data yet for this subtopic |

These boundaries are implemented in exactly one place:
`frontend/packages/types/src/mastery.ts` → `getMasteryStyle()`

They are referenced in exactly one backend place:
`backend/app/services/gap_map_service.py` → student grouping logic

**CONSTITUTION Rule:** Never hardcode `0.4` or `0.7` in component code.
Always call `getMasteryStyle()`. If thresholds change in the future, they change in one file.

---

## Why 0.7 as the Strong/Developing boundary

**Cambridge alignment:** Cambridge Assessment International Education's own performance
level descriptors for internally assessed work use a 70% threshold as the boundary between
"meeting expectations" and "exceeding expectations." Cambridge mark scheme guidance for
most IGCSE subjects gives approximately 70% of total marks as the threshold for a Grade B/C
boundary — a widely recognised academic minimum for confident subject competence.

**IB alignment:** IB MYP uses a 1–8 criterion-based scale. The boundary between achievement
level 5 ("substantial understanding") and 6 ("comprehensive understanding") maps to
approximately 70% of criterion descriptors met.

**Research basis:** Educational measurement research (Bloom's mastery learning, 1968; Guskey,
2007) consistently identifies 70–80% criterion-referenced mastery as the threshold for
"readiness to progress" to the next topic. Using 0.7 aligns with this body of work.

**Practical implication:** A student at 0.71 is placed in Group C (extension/enrichment)
in lesson plan generation. A student at 0.70 is placed in Group B (still developing).
This is the correct boundary — the test is `> 0.7`, not `>= 0.7`.

---

## Why 0.4 as the Developing/Needs Work boundary

**Cambridge alignment:** Cambridge's own "below expected standard" descriptor maps roughly
to the bottom 40% of assessment marks. Below this, students are typically unable to
demonstrate foundational understanding of the topic and require targeted re-teaching rather
than scaffolded progression.

**Lesson plan grouping:** Group A (below 0.4) in Kaihle's lesson plans requires foundational
support — different pedagogical strategy from Group B (developing). The 0.4 boundary was
chosen because below this point, students often cannot independently engage with grade-level
content and need the teacher to re-establish prerequisites. This mirrors Cambridge's own
grouping guidance for differentiated instruction.

**Study plan trigger:** When `score < 0.4`, Kaihle may suggest immediate study plan
assignment to the teacher. This threshold matches what an experienced Cambridge teacher
would consider "needs attention now" rather than "watch and monitor."

---

## Why these thresholds apply globally (not per-subject)

The alternative — subject-specific thresholds — would require a rubric for every subject
and grade combination, creating 21 different threshold tables (7 subjects × 3 grade bands).
This complexity would:
1. Confuse teachers who interpret the same colour differently per subject
2. Make parent communication inconsistent ("Strong in Maths" vs "Strong in English" would mean
   different things)
3. Require ongoing curriculum expert review as Cambridge updates syllabuses

The single-threshold approach is a deliberate simplification. It is educationally valid because:
- Cambridge's own performance level language is consistent across subjects ("above expected standard")
- Parents and students see one consistent system across their entire experience on the platform
- Teachers can apply one consistent mental model to all their classes

---

## Boundary edge cases

**Exactly 0.7 → Developing (not Strong)**
The test is `score > 0.7`. A student who scored 70% exactly is still in the developing
band. This is intentional — 70% is the minimum passing bar, not yet "strong." This aligns
with Cambridge where Grade B is typically 60–69% and Grade A starts at 70%.

**Exactly 0.4 → Developing (not Needs Work)**
The test is `score >= 0.4`. A student who scored 40% exactly is classified as Developing,
not Needs Work. This is a "benefit of the doubt" decision — a student who reached 40% has
demonstrated some foundational understanding, even if limited.

---

## When would we change these thresholds?

The thresholds could be revised in v2 based on pilot school feedback if:
1. Teachers consistently report that "Strong" students at 0.72 are still struggling
   (suggests the upper boundary needs to move to 0.75 or higher)
2. Parents report that "Developing" feels like a negative label for students above 0.6
   (suggests the lower boundary needs to move, or the label needs to change)

Any change requires:
1. Update to `frontend/packages/types/src/mastery.ts`
2. Update to `backend/app/services/gap_map_service.py` student grouping
3. Update to this document
4. A migration to recalculate all existing `gap_states` records (or accept that old data
   uses old thresholds — document which approach was taken)

---

## Implementation constraint

These thresholds MUST live in `packages/types/src/mastery.ts` only. The backend
student grouping logic (Group A/B/C in `lesson_plan_service.py`) uses the same
numeric values but is currently duplicated:

```python
# lesson_plan_service.py — current duplication
if avg < 0.4:
    groups["A"].append(student_id)
elif avg <= 0.7:
    groups["B"].append(student_id)
else:
    groups["C"].append(student_id)
```

**This duplication is a known technical debt.** In a future task, extract a
`MasteryThreshold` constant from a shared config that both frontend and backend import.
For v1, the values are explicitly documented here so that any future change is made
in both places simultaneously.

---

## Related files

| File | Role |
|---|---|
| `frontend/packages/types/src/mastery.ts` | Single source of truth for frontend thresholds |
| `frontend/packages/types/src/__tests__/mastery.test.ts` | Tests for boundary edge cases |
| `backend/app/services/lesson_plan_service.py` | Student grouping — uses same values |
| `backend/app/services/gap_map_service.py` | Gap map aggregation — uses same values |
| `docs/design/DESIGN_SYSTEM.md` §2 | Visual token reference (colours per band) |
| `docs/design/screens/TEACHER_SCREENS.md` | Gap map heatmap colour spec |
| `docs/design/screens/STUDENT_SCREENS.md` | Traffic light spec |
| `docs/design/screens/PARENT_SCREENS.md` | Traffic light spec (no numeric scores) |

---

*Mastery Threshold Rationale v1.0 · Vidhya (educational basis) + Kramer (technical implementation) · March 2026*
