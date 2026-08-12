# ADR-003 — Grade-Scoped Learning Objectives
**Date:** August 2026
**Status:** Accepted
**Authors:** Vibhu (problem framing) + Kramer (technical) + Vidhya (curriculum)
**Supersedes:** Nothing. Amends the design intent recorded in `LearningObjective`'s
model docstring (`backend/app/models/curriculum.py`).

---

## Context

The question bank was deliberately made curriculum-agnostic. Questions used to bind to
`question_bank.subtopic_id`; subtopics are curriculum PLACEMENT and are deleted whenever
a curriculum is remapped, so every remap orphaned its questions. `scripts/wipe_curriculum.py`
states it plainly: *"In-scope questions have subtopic_id set to NULL."* The fix was to
bind questions to `learning_objective_id` — the underlying CONCEPT, which survives a remap.

That solved the durability problem and introduced a new one: **a question's grade became
underivable.**

### How grade is lost

`learning_objectives.topic_id` points at `topics`, which is grade-agnostic. Subtopics point
at `curriculum_topics`, which is grade-pinned. So the objective layer is attached one level
too high in the hierarchy to carry grade.

`scripts/create_learning_objectives.py --mode new-tree` then de-duplicates using
`topic_id` alone as the bucket key:

```python
by_norm_text: dict[tuple[uuid.UUID, str], uuid.UUID]   # (topic_id, normalised_text)
matched_id = by_norm_text.get((topic_id, norm))
for candidate in by_topic.get(topic_id, []):           # cosine, also topic-scoped
```

Its docstring names the resulting behaviour as a goal:

> *"Runs staged de-duplication so the same concept appearing at several placements
> (e.g. "Ordering decimals" in both grade 6 and grade 7) resolves to ONE objective
> rather than two"*

Grade-spanning objectives are therefore **engineered output, not data drift**. Every future
`new-tree` run produces more of them. Raising the similarity threshold cannot help: Y6 and Y7
"Ordering decimals" have near-identical text *because the concept is the same* — only the
expected demand differs, which embeddings cannot see.

### Why this matters

Measured on the dev database (August 2026):

| Fact | Value |
|---|---|
| Learning objectives total | 1239 |
| Objectives spanning >1 grade | 12 |
| Of those, caused by a topic that repeats across grades | **12 (100%)** |
| Objectives reused across curricula at the same grade | **0** |
| Subtopic→objective links total | 1253 |

These are point-in-time counts from the dev database, not invariants. Re-run them before
implementing: the migration plan gates on the spanning count being exactly 12, and a different
number means the data has moved and the split step needs re-planning. (Re-verified 2026-08-12:
all five figures still hold exactly.)

**Read the 0 with care — it is structurally forced, not an observation.** Four curricula are
loaded, and they occupy strictly disjoint grade bands:

| Curriculum | Grade levels | Subtopics |
|---|---|---|
| `cambridge_primary` | 5 | 58 |
| `cambridge_lower` | 6–8 | 508 |
| `igcse` | 9–10 | 325 |
| `cambridge_as_level` | 11–12 | 362 |

No grade level is served by more than one curriculum, so "reused across curricula **at the
same grade**" had no opportunity to be anything but 0. The row establishes that nothing is
being broken today; it is not evidence that the capability is unwanted. The argument for
preserving cross-curriculum reuse rests on the design comparison below, not on this row — and
it stays prospective until a curriculum overlapping an existing grade band lands (see ADR-002,
IB curriculum roadmap).

The decisive product fact, confirmed by Vibhu: **a question can be appropriate for Year 6
and inappropriate for Year 8, even when both teach the same objective.** The original design
assumed the opposite — that one objective implies one interchangeable question pool. Under
that assumption grade-free objectives are correct. Once it is false, they are not.

`difficulty_level` does not substitute. It expresses difficulty *within* a grade, not the
demand difference *between* grades.

### Why this blocks the migration

`question_selection.py` declares the objective path canonical and `subtopic_id` deprecated.
In practice only **four** call sites have migrated — `_select_questions_for_diagnostic`
(`assessment_service.py:698`), `_load_adaptive_candidates` (`attempt_service.py:465`),
`calculate_gap_states_for_attempt` (`gap_service.py:155`), and `_fetch_check_questions`
(`mini_course_service.py:600`). Roughly **13** still join `question_bank.subtopic_id`. Those
cannot migrate while grade is underivable, and they are already failing where the remap has run:

| Scope | Questions via objectives | % NULL `subtopic_id` | Usable by legacy query |
|---|---|---|---|
| Integrated Science Y6 | 1125 | 0% | 1125 |
| Integrated Science Y7 | 1094 | 0% | 1094 |
| **Integrated Science Y8** | 121 | **100%** | **0** |
| **Mathematics Y8** | 447 | **84%** | 71 |

A populated `subtopic_id` is the signature of *legacy* mapping. Newly remapped scopes have
none, so any query still joining it silently returns zero rows.

---

## Decision

**Make grade part of the learning objective's identity, scoped as `(topic_id, grade_id)`.**

1. Add `grade_id` (FK → `grades`) to `learning_objectives`.
2. Enforce `UNIQUE (topic_id, grade_id, normalised_objective_text)` so a grade-spanning
   objective becomes impossible to create, rather than merely discouraged.
3. Re-key de-duplication in `create_learning_objectives.py` from `topic_id` to
   `(topic_id, grade_id)`, on both sides of the comparison.
4. Split the existing 12 spanning objectives; re-point their questions using surviving
   `subtopic_id` provenance where it exists, and route the remainder to human review rather
   than defaulting them to a grade (see Consequences).
5. Only then migrate the remaining selection sites off `subtopic_id`.

Grade then reaches a question as a derived property:

```
question → learning_objective_id → learning_objectives.grade_id
```

No join through any row that a curriculum rebuild deletes.

### Why `(topic_id, grade_id)` and not `curriculum_topic_id`

`grades` is a global, curriculum-agnostic table — 9 rows, `level` UNIQUE 1–13,
docstring *"Global grade levels. School-agnostic."* Curricula reference shared grade rows
via `curriculum_grades`; they do not own private ones. Keying on `grade_id` therefore adds
grade precision **without importing a curriculum dependency**.

`curriculum_topic_id` is the 4-tuple *(curriculum, subject, grade, topic)*. Keying on it
would also separate Cambridge Y7 from MYP Y7, destroying cross-curriculum reuse.

| Comparison | `topic_id` (today) | `curriculum_topic_id` | **`(topic_id, grade_id)`** |
|---|---|---|---|
| Cambridge Y6 vs Cambridge Y7 | merged ✗ | separate ✓ | **separate ✓** |
| Cambridge Y7 vs MYP Y7 | merged ✓ | separate ✗ | **merged ✓** |

Cross-curriculum reuse is a stated product requirement (Vibhu, August 2026) and is preserved.

---

## Alternatives considered and rejected

### A. Add `grade_id` to `question_bank`
**Rejected.** It assumes every curriculum agrees on what a level means. Cambridge Lower
Secondary Year 7 and IB MYP Year 2 both sit at level 7 but differ in expected demand, so
tagging a question "level 7" would not make it appropriate for both. It looks
curriculum-agnostic while silently assuming curricular equivalence.

### B. Bind questions to the `subtopic_objectives` bridge row instead of `learning_objective_id`
**Rejected.** It does express grade precisely (a subtopic pins one `curriculum_topic`).

Two problems. First, the bridge has no surrogate key to bind to — `SubtopicObjective` is a
plain `Base` with a composite primary key `(subtopic_id, learning_objective_id)` and no `id`
column, so this would require adding one. Second and decisively:
`subtopic_objectives.subtopic_id` is `ON DELETE CASCADE`, and `wipe_curriculum.py` deletes
subtopic rows during a remap — so the bridge rows cascade away and questions are orphaned.
This is the exact failure that motivated abandoning `subtopic_id`.

### C. Split the 12 spanning objectives by renaming canonical codes (`-G6`, `-G7`)
**Rejected as a complete solution; retained as a data-migration step.** It repairs today's
output without changing the generator, so the next `new-tree` run recreates the problem.
Encoding grade in a string also makes filtering an unindexable `LIKE '%-G6'` parse.
The split itself is still needed (step 4 above) — but as a consequence of the re-key,
not as the fix.

### D. Backfill question grade from legacy `subtopic_id`
**Rejected as a strategy.** A populated `subtopic_id` *is* the signature of legacy mapping;
new mappings deliberately leave it NULL. It repairs only the shrinking legacy subset and is
structurally unavailable for everything mapped from now on.

### E. Use `difficulty_level` to discriminate grade
**Rejected.** `difficulty_level` is within-grade by definition. Reusing it for cross-grade
demand would conflate two different axes and corrupt the adaptive staircase, which already
uses it per-topic.

---

## Consequences

### Positive
- Question grade becomes derivable under the new mapping, unblocking migration of the
  remaining ~13 selection sites off deprecated `subtopic_id`.
- Grade-uniqueness becomes a database invariant rather than a script convention.
- De-duplication gets sharper: candidate pool per comparison drops from **avg 9.5 / max 41**
  to **avg 4.4 / max 12**, so fewer pairs land in the 0.80–0.89 human-review band.
- Cross-curriculum objective reuse is preserved.

### Negative
- **Cross-grade objective reuse is foreclosed permanently.** This is a deliberate narrowing:
  all 12 observed sharing instances are cross-grade, and every one of them is a defect rather
  than a use case. The capability is given up by design. Note that the companion "0
  cross-curriculum reuse" figure carries no weight as evidence here — the four loaded curricula
  sit in disjoint grade bands, so same-grade cross-curriculum reuse was never possible to
  observe.
- Objective count grows 1239 → 1252. Re-key touches 25 of 1253 links (2%) and creates
  **13** new objectives. (Verified 2026-08-12.)
- **78 questions cannot be assigned a grade mechanically and need human review.** Of the 388
  questions on the 12 spanning objectives, 310 re-point cleanly via surviving `subtopic_id`
  provenance; 78 have none — concentrated in `SCI-PARTICLE-THEORY-ARRANGEMENT` (39),
  `MATH-CALCULATE-MEAN-MEDIAN` (21) and `MATH-ADD-SUBTRACT-FRACTIONS` (12). Defaulting them to
  the surviving objective's lowest grade would assign grade by accident of the split
  algorithm — the exact error this ADR exists to prevent. They go to `lo_review_items`
  as `PENDING` instead, which is a real cost: the split is not fully automatic.
- **Year 8 content gaps become visible.** Integrated Science Y8 has lost `subtopic_id`
  provenance entirely (121/121 NULL), so its share of the split lands with **zero questions**.
  This is not a regression — it exposes a real gap that the shared-objective model was
  hiding by serving Year 7 questions to Year 8 students. It requires authoring, not migration.
- The `LearningObjective` docstring — *"deliberately carries neither a difficulty range
  nor a grade range"* — becomes wrong for grade and must be updated in the same change.
- **The canonical schema does not describe the table this ADR modifies.**
  `docs/kaihle_v2_1_schema.sql` (header: v2.2, updated 2026-05-15) contains no
  `learning_objectives` and no `subtopic_objectives` table — the whole objective layer
  arrived later via migration `3670a6fac36d` and was never back-written. CONSTITUTION Rule 8
  makes that file authoritative, so adding `grade_id` and a UNIQUE constraint to it is not
  currently possible without first restoring the tables they belong to. Back-writing
  `learning_objectives`, `subtopic_objectives`, `question_bank.learning_objective_id` and
  `lo_review_items` into that file is therefore a prerequisite of this work, not a follow-up.
  This is pre-existing drift that ADR-003 surfaces rather than causes.

### Neutral
- `learning_objectives.topic_id` still points at `topics`. Nothing the objective depends on
  is deleted by a curriculum wipe, so remap durability is unchanged.
- `question_selection.py`'s module docstring is the natural home for a pointer to this ADR,
  but does not cite it today. Add the reference when `grade_id` lands, not before — the
  docstring should describe the code as it is.

---

## Related, not resolved here

`POST /classes/{class_id}/assessments` (`create_assessment`) applies
`CurriculumTopic.grade_id == class_.grade_id` **and** intersects it with teacher-selected
`topic_ids`, which are themselves `curriculum_topics.id` and already grade-pinned. The two
predicates are mutually exclusive whenever a prior grade is selected, so prior-grade
assessments return zero questions. `design_tier1_diagnostic` has no such filter and instead
validates current-or-previous grade explicitly.

That is a separate defect with its own fix (remove the redundant filter; port the explicit
validation). It is noted here because it shares a query with this work, not because this
ADR resolves it.

---

*ADR-003 · Grade-Scoped Learning Objectives · August 2026*
