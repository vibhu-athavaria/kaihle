# Running the LLM Evaluation Pipeline — Operator Runbook

**Audience:** the person running the evals (Vibhu). **Status as of 2026-10-16:** the offline harness is built and merged; **no live run has ever been executed**, so no quality number exists yet. This runbook gets you from zero to the first three measurements. The production-output pipeline (sampling real LLM output into Kaihle Admin) is only partly built — see §9.

For *why* any of this exists, read `docs/eval/LLM_EVALUATION_OVERVIEW.md`. This file is only *how*.

---

## 1. What you will run

Three live runs, **in this order** (the third reads results the second saves):

| # | Run | What it measures | File it runs | Judge calls (approx.) |
|---|---|---|---|---|
| 1 | **Grader** | Does the open-answer grader mark answers correctly? How often does it give false credit? Is its feedback constructive and does it avoid revealing the answer? | `evals/test_grade_open_answer_eval.py` | 72 grader calls + up to 144 judge calls, one after another |
| 2 | **Question calibration** | Can our question-quality judges catch *known* defects (wrong key, two correct answers, diagram reference…) that we planted in 228 computed maths questions? Also meta-tests the **production** question-quality judge. | `evals/test_question_calibration_eval.py` | about 794 rubric judge calls + 228 production-judge calls (4 at a time) |
| 3 | **Bank generation** | Takes 12 synthetic specs, generates questions through the production path, runs deterministic checks and judge rubrics on them. | `evals/test_question_bank_eval.py` | 12 generation calls + up to roughly 500 judge calls |

Roughly **1,500–1,800 LLM calls in total**. Multiply by your per-call price to budget it (§7). Time was not measured; the grader run is sequential, the other two run 4 calls at a time.

Every run writes a Markdown report to `backend/evals/reports/` (git-ignored). Run 2 also saves per-rubric **calibration files** to `backend/evals/reports/calibration/`; Run 3 reads them to label each rubric `CALIBRATED`, `INDICATIVE` or `MISSING`.

---

## 2. What you need (checklist)

- [ ] **A judge model** from a *different model* than the one under test, and preferably a *different vendor* (the harness refuses identical models and warns on the same vendor). Format is the LiteLLM string, for example `openrouter/<vendor>/<model>`.
- [ ] **Provider API key(s)** for every model you use, in `backend/.env` (for example `OPENROUTER_API_KEY=…`). The judge and the models under test all go through `app/ai/providers/router.py`.
- [ ] **All of these model variables set (non-empty)** in `backend/.env`. The independence guard refuses to start if a task has no model:

  | Variable | Needed by | Note |
  |---|---|---|
  | `LLM_EVAL_JUDGE_MODEL` | all three runs | the judge. Leave `LLM_EVAL_JUDGE_API_BASE` empty unless self-hosting |
  | `LLM_GRADE_OPEN_ANSWER_MODEL` | run 1 | has a default; the grader under test |
  | `LLM_QUESTION_GENERATION_MODEL` | runs 2 and 3 | **empty by default** |
  | `LLM_QUESTION_QUALITY_MODEL` | run 2 | **empty by default**; the *production* judge being meta-tested |
  | `LLM_QUIZ_GENERATION_MODEL` | run 2 | **empty by default**; run 2's preflight checks it even though the quiz path is not evaluated yet |

  The judge must differ from **every** model above. If you use one model for all your app tasks, pick a different one for the judge.
- [ ] **Python tooling:** `uv`, Python 3.12.
- [ ] **No database or Docker needed** for runs 1–3. They do not touch Postgres. (Only needed if you also want cost rows in Kaihle Admin → LLM Logs: set `LLM_USAGE_TRACKING_ENABLED=true` and have Postgres running. Optional.)
- [ ] **A few dollars of credit** and a spending limit on the provider key. See §7.

`DEEPEVAL_TELEMETRY_OPT_OUT=YES` is forced by the harness; you do not need to set it, but `.env.example` keeps it for your shell.

---

## 3. One-time setup

Always from the `backend/` directory of a checkout that has the merged eval code:

```bash
cd /Users/vibhu/Projects/kaihle/backend
git checkout main && git pull origin main
unset VIRTUAL_ENV
uv sync --all-extras --group eval --python 3.12
```

`--group eval` installs DeepEval (it is intentionally **not** in the production image). `--all-extras` matters: without it `uv run mypy` silently uses a global mypy.

Create or edit `backend/.env` with the variables from §2. Settings are read from `.env` in the directory you run from, so **run every command below from `backend/`**.

---

## 4. Preflight (no LLM calls, free)

Do this before spending anything.

**4a. Offline harness tests** (all mocked, should be green):

```bash
uv run --group eval pytest evals/tests -q
```

Expect all tests to pass (313 at the time of writing). If not, stop; fix that first.

**4b. Configuration check** (reads settings only, makes no calls):

```bash
uv run --group eval python -c "
from evals.judge import judge_config_problem as p
for t in ('grade_open_answer', 'question_generation', 'question_quality', 'quiz_generation'):
    print(t, '->', p(t) or 'OK')
"
```

Every line must say `OK`. Typical messages and what they mean:

| Message | Fix |
|---|---|
| `LLM_EVAL_JUDGE_MODEL is not set` | set the judge in `.env` |
| `No model is configured for graded task 'x'` | set that task's `LLM_*_MODEL` |
| `Judge model is identical to the model under test…` | choose a different judge |

(The same-vendor case only prints a warning at run time, not here. Prefer a different vendor anyway.)

**4c. Confirm live tests are no longer skipped**, still free:

```bash
uv run --group eval pytest evals/test_grade_open_answer_eval.py -rs
```

If you still see `SKIPPED … live eval skipped: …`, the message tells you what is missing. When it instead starts running (it will then spend money), press Ctrl-C if you are not ready.

---

## 5. The three runs

Run each in its own command, in order. They are real LLM calls and cost money. `-v` shows test names; `-rs` explains skips.

### Run 1 — Grader

```bash
uv run --group eval pytest evals/test_grade_open_answer_eval.py -v -rs
```

- **Report:** `evals/reports/grade_open_answer_<timestamp>.md`.
- **Read first:** the *Accuracy* and *False credit* sections (how often a wrong answer is marked correct is the headline risk: it inflates mastery), then *Parse failure*, then the *G-Eval feedback rubrics* table.
- **The test passing means only** that every case produced an outcome and the report was written. It does *not* mean quality is good. Quality figures are report-only.
- **If it stops with `JudgeUnusableError`:** every judge verdict for a rubric was unparseable. The judge model is probably returning something the harness cannot read (very small model, or a model that wraps answers in prose). Try a stronger judge before suspecting the grader.

### Run 2 — Question calibration (do this before run 3)

```bash
uv run --group eval pytest evals/test_question_calibration_eval.py -v -rs
```

- **Report:** `evals/reports/question_calibration_<timestamp>.md`.
- **Also writes** `evals/reports/calibration/*.json`, one per rubric. Do not delete these before run 3.
- **Read first:** the *Rubric calibration* table. For each rubric: recall (does it catch the planted defect?), false-alarm rate (does it wrongly fail clean questions?), indeterminate count, **n**, and **status**. Then *Cross-talk* (does a defect trip the wrong rubric?) and *Production question_quality judge* (how well the judge that already runs in production does on the same questions).
- **Remember the caveat printed in the report:** defects were planted synthetically and are *easier* than real ones, so recall here is an **upper bound**.
- Status meanings: `CALIBRATED` (enough samples, recall lower bound ≥ 0.70, false-alarm upper bound ≤ 0.15), `INDICATIVE` (measured only on model-authored, unvalidated labels), `INSUFFICIENT_N`, `NOT_CALIBRATED` (failed the thresholds), `STALE` (rubric text changed since calibration), `MISSING`.

### Run 3 — Question-bank generation

```bash
uv run --group eval pytest evals/test_question_bank_eval.py -v -rs
```

- **Report:** `evals/reports/question_generation_bank_<timestamp>.md`.
- **Read first:** *Structural outcomes* (did generation return parseable questions at all; true/false questions are set aside and counted), then *Deterministic checks* (cheap, trustworthy), then *Judge rubrics*. Any rubric that is not `CALIBRATED` is marked **UNCALIBRATED — indicative only**: do not quote its number as a quality score.
- If every rubric shows `MISSING`, run 2 has not been run on this machine (or its `reports/calibration/` folder was deleted).

---

## 6. After the runs

1. **Keep the reports.** They are git-ignored on purpose (they can contain generated text). Copy them somewhere safe if you want a record.
2. **Send them to me** (paste or attach the three `.md` files). I will:
   - record the findings and judge noise,
   - flag harness bugs the first live run exposes (expect a few; nothing has run live before),
   - propose the pass floors (decision **OD-1**: floors are set *after* first measurements).
3. **Re-run run 1 or 2** once, with no code changes, to see how much the numbers move between identical runs. That judge noise matters for every threshold we set. (This costs the same again.)
4. Do **not** change thresholds (`MIN_N=20`, recall lower bound 0.70, false-alarm upper bound 0.15) to make a rubric turn green. They are pre-registered.

---

## 7. Cost and safety

- **Estimate cost** before running: calls (table in §1) × your judge's per-call price. If your judge is unpriced in LiteLLM, find its price from the provider and compute by hand. Set a hard spending limit on the provider key first.
- **If you want the cost visible in the app:** set `LLM_USAGE_TRACKING_ENABLED=true` with Postgres running; judge calls then appear in Kaihle Admin → LLM Logs as task `eval_judge`, component `eval_harness`.
- **What goes to the judge:** runs 1–3 use only the repo's synthetic datasets (`evals/datasets/`). **No real student data is used.** Nothing here reads production data.
- **Never commit** anything under `backend/evals/reports/`.
- **Ctrl-C is safe.** A stopped run leaves earlier calibration files intact; a calibration file is written atomically per rubric, so a half-written file cannot appear.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| All 4 live tests `SKIPPED` | judge or graded model not configured | §4b tells you which |
| `JudgeNotIndependentError` | judge model equals a model under test | use a different judge |
| `JudgeConfigError … No model is configured for graded task` | one of the empty-by-default model variables | set it (§2 table) |
| `ModuleNotFoundError: deepeval` | forgot `--group eval` | re-run `uv sync … --group eval` and use `uv run --group eval` |
| Authentication or 401 errors | missing or wrong provider key in `backend/.env` | check key name matches the provider |
| `JudgeUnusableError` | judge replies unreadable | stronger judge; look at the exact reply in the logs |
| Run 3 shows every rubric `MISSING` | run 2 not done on this machine | run 2 first |
| Many rubrics `STALE` | rubric wording changed since the last run 2 | re-run run 2 |
| `mypy`/`ruff` complaints when you contribute | wrong environment | `unset VIRTUAL_ENV`, `uv sync --all-extras --group eval --python 3.12` |
| A single call hangs | provider outage | the router times out after `LLM_REQUEST_TIMEOUT_SECONDS` (default 120) and the error surfaces; just re-run |

---

## 9. The production-output pipeline (what is and is not available)

Runs 1–3 use **synthetic** data. The pipeline you described as the real goal — sampling **real production LLM output**, scrubbing it, judging it and showing results in **Kaihle Admin** — is built in stages:

| Piece | Branch | State |
|---|---|---|
| Admin-settable monthly eval budget (`GET/PUT /api/v1/platform/eval-settings`, default 0, fail-closed) | `MLH-T18_feature/platform-settings-budget` | merged (#284) |
| `eval_runs` / `eval_results` tables | `MLH-T18_feature/eval-results-tables` | merged (#289) |
| PII scrubber + seeded sampler | `MLH-T18_feature/scrubber-and-sampler` | merged (#292) |
| Budget guard, evaluator registry, app-side judge guards | `MLH-T18_feature/budget-guard-registry` | built, awaiting commit/merge at time of writing |
| Rubrics usable from the product, runner + Celery + weekly schedule | slices 5a / 5b | not built |
| Read APIs, Kaihle Admin "Quality" page | slices 6 / 7 | not built |

**When it is complete you will need, in addition to §2:** Postgres and the backend running; `LLM_USAGE_TRACKING_ENABLED=true`; a **non-zero monthly budget** set in Kaihle Admin (it is 0 by default and every run is refused until you raise it); `LLM_EVAL_JUDGE_MODEL` set on the deployed backend; the student-text acknowledgement switched on in the eval settings before any task that includes student-typed text is evaluated; and `EVAL_UNPRICED_CALL_COST_USD` set to your real judge cost (default is a deliberately high 1.0 USD). Only rubrics that runs 2 showed to be `CALIBRATED` (or `INDICATIVE`, if you enable that flag) will be applied to production rows, so **run 2 is also the gate for the production pipeline.**

I will extend this section with exact steps when slices 5–7 are merged.

---

## 10. One-page summary

```bash
cd /Users/vibhu/Projects/kaihle/backend && git checkout main && git pull origin main
unset VIRTUAL_ENV && uv sync --all-extras --group eval --python 3.12
# edit backend/.env: judge model, provider key, the 5 model vars in §2
uv run --group eval pytest evals/tests -q                        # free, must be green
uv run --group eval python -c "from evals.judge import judge_config_problem as p; [print(t, p(t) or 'OK') for t in ('grade_open_answer','question_generation','question_quality','quiz_generation')]"
uv run --group eval pytest evals/test_grade_open_answer_eval.py -v -rs        # run 1 (costs money)
uv run --group eval pytest evals/test_question_calibration_eval.py -v -rs     # run 2 (costs money)
uv run --group eval pytest evals/test_question_bank_eval.py -v -rs            # run 3 (costs money)
ls evals/reports/                                                             # send me these
```
