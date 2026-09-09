# Mastery Model Rationale
**MLH-T3** · 2026-09-09

Companion to `MASTERY_THRESHOLD_RATIONALE.md`, which documents the *display bands*
(0.4 / 0.7, Cambridge/IB-cited) — those are unchanged by this work. This document covers
the *estimator* underneath the bands: how `gap_states.mastery_score` and `.confidence` are
actually computed, and the four things measuring the old approach found.

---

## What was replaced

`gap_service.py` computed mastery from six undocumented coefficients:

```python
mastery = current_score * 0.7 if is_diagnostic else current_score * 1.0
mastery = (current_score * 0.65) + (historical[0] * 0.35)
mastery = (current_score * 0.5) + (historical[0] * 0.3) + (historical[1] * 0.2)
confidence = min(rolling_attempt_count / 5.0, 1.0)
```

Each was a hand-rolled approximation of something a Beta-Binomial posterior does exactly:
the `× 0.7` discount approximates *shrinkage toward a prior*; the weighted-average sets
approximate *recency weighting*; `min(n/5, 1)` approximates *posterior variance*. The
replacement (`app/services/mastery_model.py`) collapses these into one estimator with two
interpretable parameters — a Beta prior `(α, β)` and a recency `decay` — rather than six
opaque ones, and confidence stops being computed independently of the score it describes.

---

## Finding 1 — the Strong band was mathematically unreachable

`max(gap_states.mastery_score)` across every row before this work was **exactly 0.700**.
Every student's first diagnostic ran the `× 0.7` path; a perfect 1.0 became exactly 0.700;
the Strong band requires `> 0.7`. **A student who answered every question correctly could
never be shown as Strong.**

This is fixed as a side effect of removing the multiplier, not by anything specific to the
estimator chosen — any replacement without a hard ceiling at 0.7 would have fixed it. Under
the Beta-Binomial posterior, a perfect 10/10 with no calibrated prior yet resolves to
`(10+2)/(10+2+0+3) = 0.8` — comfortably inside Strong, as a consequence of the model rather
than a hand-picked exception.

---

## Finding 2 — method-of-moments calibration is a trap; MLE on counts is not

The plan called for fitting the prior empirically rather than choosing it by taste. The
first attempt — method of moments on per-subtopic **proportions** — returned:

```
Beta(0.058, 0.055)   strength 0.11
```

A prior this weak applies almost no shrinkage, defeating the purpose of having one. The
cause: 77% of per-subtopic observations rest on exactly one response, which can only score
0.0 or 1.0. A proportion-based fit sees this as a genuinely bimodal population and
concludes there is no real spread to shrink toward — encoding the exact defect the model
exists to remove, fed back in as "the data."

**Beta-Binomial MLE fit directly on `(correct, total)` counts** does not have this failure
mode, because it models the sampling noise explicitly — a 0/1 observation is correctly
weak evidence rather than a measurement at the extreme. On the same data:

```
Beta(2.68, 2.60)   strength 5.28   log-likelihood -922
```

against the originally-guessed `Beta(2, 3)` (mean 0.400, strength 5.00, log-likelihood
-951). MLE wins decisively, and the fitted strength (5.28) landing near the old
`min(n/5, 1)` ramp's implied strength (5) is a genuinely nice result — whoever wrote that
ramp had a correct instinct about how much evidence earns confidence, expressed as a magic
number instead of a prior.

**Verdict:** proportions are the wrong unit to fit on. Fit on counts.

---

## Finding 3 — pooling within the curriculum graph needs a floor *and* a ceiling

The natural next question: subtopics are sparse (n≈1 typically), but they sit inside a
curriculum graph. Surely pooling across subtopics within the same topic or subject gives a
better local prior than one flat global number.

| Level | Scale measured | MLE result |
|---|---|---|
| Subtopic | 225 subtopics, mostly n=1 | Never enough data alone |
| Topic | 62 topics, 15–34 responses each | **Still too thin** — below a 100-row floor |
| Subject: MATH | 631 responses | `Beta(1.80, 2.35)` — clean |
| Subject: SCI | 408 responses | **`Beta(2346, 1341)` — degenerate** |
| Subject: ENG | 15 responses | No fit attempted |
| Global | 1041 responses | `Beta(2.68, 2.60)` — clean |

The SCI result is a second bug, caught by running the fit rather than trusting the formula.
Strength 3687 asserts near-certainty that every SCI student scores 63.6% — an absurd claim
from 15 distinct subtopics and 15 students. Unconstrained MLE has no ceiling: a sample with
little genuine between-row variance beyond binomial sampling noise makes the likelihood
improve monotonically toward an unbounded, near-point-mass solution. (Confirmed
independently while writing this estimator's own test fixtures: a pool of *identical,
repeated* rows — no real diversity — reproduces the same degenerate shape on command; real
between-student variance is what keeps a fit finite.)

**Consequence:** every per-level fit needs a floor (`α+β ≥ 2`, weaker than uniform is
useless) **and** a ceiling (`α+β ≤ 4 × row count`, calibrated against this one observed
failure — a starting point, not a tuned constant). `fit_beta_mle` also bounds its own
search space so a degenerate sample terminates quickly rather than searching indefinitely
toward the unbounded optimum.

On this data, the backoff chain (`SUBTOPIC → TOPIC → SUBJECT → GLOBAL`) resolves 385
subtopics (all of MATH's) to a subject-specific prior, and the remaining 868 back off to
GLOBAL. Both counts match the curriculum's actual per-subject subtopic totals exactly. This
is the correct, non-arbitrary outcome at current pilot scale — not a failure of the
approach — and it upgrades automatically as more response data accumulates.

---

## Finding 4 — most of the curriculum has zero data, and a one-time fit goes stale

10 subjects exist; only 3 (MATH, SCI, ENG) have any response data. **7 of 10 — BIO, CHEM,
ENGL, GEO, GP, HIST, PHY — have zero**, roughly 900 of 1253 active subtopics. This is not
"thin," it is "none," and it forced two decisions:

1. **The calibration script writes a row for every active subtopic, unconditionally** —
   including the 900 with zero data, resolving to `GLOBAL`. Without this, `gap_service`
   would need a "row missing" branch exercised by the *majority* of subtopics on day one —
   exactly the implicit fallback `.claude/rules/01-core-principles.md` prohibits.
2. **A fit computed once goes stale.** The moment a school starts using Biology
   diagnostics, Biology should graduate from `GLOBAL` to its own prior — nothing else
   triggers that. `recalibrate_mastery_priors` runs weekly via Celery Beat (the same
   pattern `check-stale-video-links` already uses), re-fitting from current data on the
   same code path the manual script uses.

---

## What was considered and set aside

A joint two-way (student × subtopic) crossed-random-effects model — equivalent to a
Rasch/1PL IRT fit, and the textbook-complete answer to "pool across both students and
items simultaneously" — was considered. With 23 distinct students in the dataset this
model is not identifiable, and Finding 3 shows even a single per-level Beta fit needs real
numerical care (a floor *and* a ceiling, a bounded search). Stacking a harder-to-validate
joint model on top of that risk is not proportionate at this data volume. Revisit once
distinct-student count is comfortably past today's 23.

---

## What did not change

- **Display bands** (`> 0.7` Strong, `0.4–0.7` Developing, `< 0.4` Needs Work) — untouched.
  Nothing in these findings suggests the boundaries are wrong, only the number being
  compared against them.
- **The confidence affordance** (dashed border on low-confidence cells, MLH-T6) — untouched
  mechanism, now fed a number that means what it claims rather than a 3-attempt-capped
  ramp.

## What this does not fix, on purpose

Two structural issues surfaced during this work and are **out of scope here** —
recorded so they are not lost, not silently implemented:

- **Diagnostic question allocation.** Questions are allocated per topic
  (`questions_per_topic`, default 5); mastery is computed per subtopic. A topic with 5
  subtopics yields ~1 question per subtopic — the actual reason estimates are thin, no
  matter which estimator is used. This dominates every lever measured in this work and is
  the highest-value next step, but it is a diagnostic-design change, not a calculation
  change, and needs Vidhya's input (the existing rule: never fewer than 3 questions per
  subtopic).
- **Difficulty label recalibration.** Within-student correlation between labelled
  `difficulty_level` and correctness is **−0.010** across 1587 responses — no signal.
  `adaptive_selector.py`'s 1-up/2-down staircase is stepping through levels that do not
  differ in real difficulty. Either fit item difficulty from response data (a Rasch model
  is tractable at this response volume) or drop the dimension.

---

## Production rollout

This is deterministic work — a pure function of `student_responses` plus curriculum
tables, both already in prod. Per the project's promotion strategy, deterministic work
runs directly on prod; there is no data artifact to export.

Deliberately **not** a migration-safe backfill: no old-formula replay, no before/after
band-change gate, no dual-write mode. Kaihle is pre-launch pilot data — the goal is that
school admins and teachers see an accurate number, not that today's (buggy) number
survives. What remains, because it is operational safety rather than a compatibility
question: a `pg_dump` of `gap_states` and `student_attempt_subtopic_scores` before
applying, `--dry-run` by default, and idempotency (see `scripts/rebuild_mastery.py`).

Scores will move, in both directions, for real reasons — the unreachable-Strong-band fix
and the corrected coefficients both move numbers. A short teacher-facing changelog should
accompany the rollout; drafted alongside this document, sent by Vibhu.
