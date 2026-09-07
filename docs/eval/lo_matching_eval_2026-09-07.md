# Learning-Objective Matching — Evaluation Report
**Date:** 2026-09-07
**Harness:** `backend/scripts/eval_lo_matching.py`
**Database:** dev (`localhost:5433`)
**Remap artifact:** `backups/question_remap_llm_decisions_20260803_0151.json`
**Task:** MLH-T1
**Labels:** `docs/eval/lo_matching_adjudicator_labels_2026-09-07.csv` (committed alongside — `backups/` is gitignored, and the evidence must travel with the conclusion)

---

## 1. What Was Measured, and What Was Not

Read this section before quoting any figure below.

| Band | Similarity | Population | Labels available | Measured here |
|---|---|---|---|---|
| Auto-bind | `>= 0.85` | Groups bound with no review | **None** — never entered any queue | ❌ Not measured |
| Adjudicated | `0.60 – 0.85` | 27 groups / 927 questions | Hand-labelled for this report (§3) | ✅ **Measured** |
| Review queue | declines + un-adjudicated | 54 items | 1 resolved of 54 | ❌ Insufficient |
| Unmatched | `< 0.60` | Reported, left unbound | n/a | n/a |

**No accuracy figure could be stated from currently stored data** — §2 explains why that is
structural rather than an oversight. The adjudicated band was therefore labelled by hand for
this report, and §3 gives its precision. The auto-bind band remains unmeasured.

### ⚠️ Provenance of the labels — read this before citing the precision figure

The 27 adjudicated groups were labelled by Claude applying the project's Vidhya curriculum
persona, not by an independent human expert. **These are model-generated labels evaluating
model-generated decisions, which is circular.**

It is not worthless: the labeller saw one decision at a time with full objective text, was
instructed adversarially, had no time pressure, and was a different invocation with different
framing from the adjudicator. It found errors the adjudicator missed. But it shares an
architecture and training distribution with the system under test, and could plausibly share
blind spots.

**Vibhu or Vidhya should spot-check at minimum the three `wrong` rulings and the largest
`unsure` (279 questions) before this figure is presented as validated.** Until then, treat
§3 as a strong first pass, not ground truth.

---

## 2. The Ground Truth I Expected Does Not Exist

The task was planned on the assumption that `lo_review_items` held free labelled pairs:
`llm_suggested_code` (what the model picked) against `chosen_objective_id` (what a reviewer
picked). It does not.

### 2.1 `llm_suggested_code` is NULL on every row

```
        item_type         |  status  | count | with_suggestion
--------------------------+----------+-------+-----------------
 OBJECTIVE_GRADE_SPLIT    | APPROVED |     1 |               0
 OBJECTIVE_GRADE_SPLIT    | PENDING  |     4 |               0
 QUESTION_REMAP           | PENDING  |    37 |               0
 QUESTION_REMAP           | SPLIT    |     6 |               0
 QUESTION_REMAP_REMAINDER | PENDING  |     3 |               0
 QUESTION_REMAP_REMAINDER | SPLIT    |     3 |               0
```

`scripts/map_questions_to_lo.py:328` passes `llm_suggested_code=None` unconditionally.

**This is correct, not a bug.** Tracing the pipeline explains why: a group the model
successfully adjudicates is *bound immediately and never queued*. Only declines and
un-adjudicated groups reach the queue. By construction, the queue contains exactly the
decisions the model did not make — so it can never evidence the decisions it did.

### 2.2 The queue is 98% unworked

53 of 54 items are `PENDING` or `SPLIT`. The single `APPROVED` item is an
`OBJECTIVE_GRADE_SPLIT`, not a question remap. There is no body of human rulings to compare
anything against.

### 2.3 Where the adjudicator's record actually lives

`backups/question_remap_llm_decisions_20260803_0151.json` — **27 groups covering 927
questions**, each with the old objective, the chosen objective, the model's stated
confidence, and its one-line reason.

Every one of those 927 questions is bound in the live question bank on the strength of an
unreviewed model decision.

---

## 3. Measured: Adjudicator Precision

All 27 adjudicated groups were labelled (a census, not a sample — n is small enough that
sampling error was avoidable). See the provenance caveat in §1.

```
LO MATCHING — PRECISION, ADJUDICATED (0.60-0.85) BAND (hand-labelled)

  0.60-0.70    70.0% [39.7–89.2] (n=10)   {'correct': 7, 'wrong': 3, 'unsure': 2}
  0.70-0.80   100.0% [51.0–100.0] (n=4)   {'correct': 4, 'wrong': 0, 'unsure': 3}
  0.80+       100.0% [64.6–100.0] (n=7)   {'correct': 7, 'wrong': 0, 'unsure': 1}

  OVERALL               85.7% [65.4–95.0] (n=21)
  WEIGHTED BY QUESTIONS 67.8% [63.7–71.6] (n=531)

  Unsure       22.2% [10.6–40.8] (n=27)  (396 questions)
```

### 3.1 The headline: 85.7% of decisions, but only 67.8% of questions

| | Groups | Questions |
|---|---|---|
| Correct | 18 | 360 |
| Wrong | 3 | 171 |
| Unsure | 6 | 396 |

The 18-point gap between decision-level and question-level precision exists because **the
errors landed on the large groups**. One wrong call carried 115 questions on its own.

This is exactly what blast-radius weighting was built to surface, and it is the number to
quote: roughly a third of adjudicated questions are bound on a decision a curriculum
reviewer would reject.

### 3.2 Every error is below 0.70 similarity

| Verdict | Similarities |
|---|---|
| Wrong | 0.638, 0.647, 0.661 — **max 0.661** |
| Correct | 0.615 … 0.844 — min 0.615 |

Nothing the model chose above 0.661 was wrong. Both strata above 0.70 are 100% correct.

The bands do overlap — the lowest *correct* decision (0.615) sits below the highest *wrong*
one (0.661) — so similarity alone does not separate them. But as a routing threshold it is
clean: **everything above 0.70 was right.**

#### Recommendation: raise `LLM_FLOOR` from 0.60 to 0.70

Counterfactual on this dataset:

| | |
|---|---|
| Groups rerouted to human review | 12 |
| Mis-bound questions caught | **171 (all of them)** |
| Correct questions sent for needless review | 118 |

A 171-to-118 trade is strongly favourable given the asymmetry the pipeline is built around:
a wrong binding is silent, permanent, and undetectable downstream, while a needless review
costs a reviewer a minute. `map_questions_to_lo.py`'s own docstring already states the
principle — *"Prefer declining over a loose match"* — and 0.60 does not honour it.

**Not changed in T1.** T1 measures; the change is a follow-up with its own review.

### 3.3 Every error is the same error

All three wrong bindings, and most of the six unsure ones, share one shape: **the old
objective is compound, and the chosen new objective covers only one of its components.**

| Old objective | Chosen | What was dropped |
|---|---|---|
| Place value to 7 digits **AND** ordering pos/neg integers | Negative numbers in context | Place value — the *leading* skill, 115 questions |
| Cell components (unrestricted) | Structures of a **plant** cell | Animal cells |
| Elements, compounds **AND** mixtures | Compound vs mixture | Elements |

The third case is notable: the model's own stated reason names the plant-cell restriction
and proceeds anyway.

**This is a fixable prompt-design gap, not a model capability gap.** `lo_matching.jinja2`
offers exactly two actions — pick a candidate, or decline. A compound source objective has
no correct move: the model cannot say "this splits across two objectives," so it picks the
best partial match and reports high confidence. The 22% unsure rate has the same cause; six
groups could not be ruled on from objective text alone because the source objective bundles
several skills.

Worth noting the pipeline already has the machinery for this — `OBJECTIVE_GRADE_SPLIT` and
`QUESTION_REMAP_REMAINDER` item types exist for per-question adjudication. The adjudication
prompt simply has no way to route into it.

---

## 3A. Finding: Self-Reported Confidence Carries No Information

| Stated confidence | Groups | Precision |
|---|---|---|
| `high` | **27 (100%)** | 85.7% |
| `medium` | 0 | — |
| `low` | 0 | — |

The prompt asks for `high`/`medium`/`low`. The model answered `high` every time — including
on all three decisions a reviewer rejected, and on the 115-question place-value error.

**A confidence label that never varies cannot inform anything.** It cannot gate what skips
review, and displaying it to a reviewer implies a discrimination the model is not performing.

This is a well-known failure mode of asking a model to self-rate after committing to an
answer. If a usable signal is wanted, the options are to elicit it before the choice, derive
it from candidate score margins, or drop the field.

### Sanity check — routing behaved as designed

Similarity of the candidate actually chosen: min 0.615, median 0.725, max 0.844. Every
adjudicated decision sits strictly inside the `0.60 – 0.85` band; zero leakage either side.
The *routing* logic is provably correct. It was the *model inside the band* that was
unmeasured.

---

## 4. Review-Queue Metrics (reported for completeness — n is too small to use)

```
Resolved items: 1

  agreement                  0
  declined_confirmed         0
  declined_recovered         1
  disagreement               0
  suggested_rejected         0
  unresolved                53

Adjudicator agreement          0.0% [0.0–100.0] (n=0)
  ...weighted by question count 0.0% [0.0–100.0] (n=0)
Decline rate                   100.0% [20.7–100.0] (n=1)
Decline recoverability         100.0% [20.7–100.0] (n=1)
Rejection rate                 0.0% [0.0–79.3] (n=1)
```

The Wilson intervals are doing their job here: `100.0% [20.7–100.0] (n=1)` is transparently
worthless, where a bare "100%" would have looked like a result. **Quote none of these.**

---

## 5. What Happens Next

### 5.1 Validate the labels — highest priority

`docs/eval/lo_matching_adjudicator_labels_2026-09-07.csv` carries a `verdict` and a
`labeller_note` for all 27 rows. Given the circularity caveat in §1, a human pass over the contested rows is what
converts §3 from a strong first pass into a citable figure:

- The **3 `wrong`** rulings (171 questions) — do you agree these are mis-bound?
- **MATH-GEO-G6-04** (`unsure`, **279 questions**) — the single largest group. Resolving it
  moves the weighted figure more than everything else combined.
- The other five `unsure` rows (117 questions)

Re-run after any change:

```bash
python -m scripts.eval_lo_matching --mode score-sample --in ../backups/eval_adjudicator_labels.csv
```

The row that best shows the difficulty:

| | |
|---|---|
| Old | *"Understand the value of each digit in integers up to 7 digits; order and compare positive…"* |
| Chosen | *"Order and use negative numbers in practical contexts such as temperature and elevation…"* |
| Model reason | *"Both objectives focus on ordering and comparing positive and negative integers on a number line"* |
| Similarity | 0.638 · Confidence `high` · **115 questions** |

Labelled **wrong**: place value is the leading skill in the old objective and the chosen
objective does not assess it at all. 115 questions — the largest single error found.

### 5.2 The auto-bind band still has no labels

`--mode export-sample` recovers the auto-bound population by elimination against the remap's
report files (auto-binds are never written down; everything else is, so the complement is
exact) and re-derives similarity by re-embedding the old objective text against the stored
new-side vectors.

It aborts if any recovered similarity falls below 0.85, which would mean the embedding
configuration has drifted since the remap and the scores describe a different model.

Not run in this pass: it needs `question_subtopic_snapshot_<ts>.json`, which is not present
in `backups/`. **Locate that snapshot to measure the auto-bind band.**

### 5.3 Recommended changes — deliberately not made in T1

| # | Change | Why |
|---|---|---|
| 1 | Persist auto-bind decisions to a report file | The band cannot be audited without reconstruction, and reconstruction is only possible while the embedding config is unchanged |
| 2 | Record the adjudicator's choice on the bound rows | Today it survives only in a JSON file in `backups/`. That is the whole evidence base for 927 questions |
| 3 | Reconsider the confidence field | Measured flat at `high` across all 27 decisions (§3A). Drop it, elicit before the choice, or derive from score margins |
| 5 | **Raise `LLM_FLOOR` 0.60 → 0.70** | Would have caught all 171 mis-bound questions for 118 needless reviews (§3.2) |
| 6 | **Give the prompt a way to say "this splits"** | Every error is a compound old objective mapped to one component (§3.3). The split machinery exists; the prompt cannot reach it |
| 4 | Work the review queue | 53 pending items, several `SPLIT`, blocking questions from reaching students |

T1 measures. It changes no threshold, no prompt, and no data.

---

## 6. Harness Verification

| Check | Result |
|---|---|
| Unit tests | 71 passed |
| Integration tests | 4 passed |
| Full backend unit suite | 1213 passed, no regressions |
| `ruff` / `mypy` | clean |
| Read-only | Verified by integration test: table snapshot identical before and after two runs |

---

## 7. Honest Summary

**What holds up.** The embedding thresholds are calibrated against measured distributions and
the routing behaves exactly as specified — every adjudicated decision landed strictly inside
its band. Above 0.70 similarity, the adjudicator made no errors at all.

**What does not.** 85.7% of adjudicated decisions were right, but only **67.8% of the
questions** those decisions govern — the errors concentrated on the large groups. Every error
sits below 0.70, and every error is the same error: a compound source objective mapped to a
new objective covering one of its parts. The model reported `high` confidence on all 27
decisions including every error, so its own uncertainty signal is not evidence of anything.

**What this points to.** Two concrete changes, both cheap: raise `LLM_FLOOR` to 0.70, and
give the adjudication prompt a way to say "this objective splits" — the pipeline already has
the item types to handle that answer, but the prompt cannot produce it.

**What is still unknown.** The auto-bind band (`>= 0.85`) has never been evaluated, and the
labels behind §3 are model-generated and need human validation. Both are named in §5.
