# ADR-003 — Grade-Scoped Learning Objectives
**Date:** August 2026
**Status:** Accepted
**Authors:** Vibhu (problem framing) + Kramer (technical) + Vidhya (curriculum)
**Supersedes:** Nothing. Amends the design intent recorded in `LearningObjective`'s
model docstring (`backend/app/models/curriculum.py`).
**Referenced in:** CONSTITUTION.md §13, `backend/app/services/question_selection.py`

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

The decisive product fact, confirmed by Vibhu: **a question can be appropriate for Year 6
and inappropriate for Year 8, even when both teach the same objective.** The original design
assumed the opposite — that one objective implies one interchangeable question pool. Under
that assumption grade-free objectives are correct. Once it is false, they are not.

`difficulty_level` does not substitute. It expresses difficulty *within* a grade, not the
demand difference *between* grades.

### Why this blocks the migration

`question_selection.py` declares the objective path canonical and `subtopic_id` deprecated.
In practice only **one** call site has migrated (`_select_diagnostic_pool`); roughly 13 still
join `question_bank.subtopic_id`. Those cannot migrate while grade is underivable, and they
are already failing where the remap has run:

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
   `subtopic_id` provenance.
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

### B. Bind questions to `subtopic_objective_id` instead of `learning_objective_id`
**Rejected.** It does express grade precisely (a subtopic pins one `curriculum_topic`).
But `subtopic_objectives.subtopic_id` is `ON DELETE CASCADE`, and `wipe_curriculum.py`
deletes subtopic rows during a remap — so the bridge rows cascade away and questions are
orphaned. This is the exact failure that motivated abandoning `subtopic_id`.

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
- **Cross-grade objective reuse is foreclosed permanently.** This is a deliberate narrowing.
  It has never occurred in practice (0 cross-curriculum reuse observed; all 12 sharing
  instances are cross-grade), but the capability is given up by design.
- Objective count grows 1239 → ~1252. Re-key touches 25 of 1253 links (2%) and creates
  **13** new objectives.
- **Year 8 content gaps become visible.** Integrated Science Y8 has lost `subtopic_id`
  provenance entirely (121/121 NULL), so its share of the split lands with **zero questions**.
  This is not a regression — it exposes a real gap that the shared-objective model was
  hiding by serving Year 7 questions to Year 8 students. It requires authoring, not migration.
- The `LearningObjective` docstring — *"deliberately carries neither a difficulty range
  nor a grade range"* — becomes wrong for grade and must be updated in the same change.

### Neutral
- `learning_objectives.topic_id` still points at `topics`. Nothing the objective depends on
  is deleted by a curriculum wipe, so remap durability is unchanged.

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
