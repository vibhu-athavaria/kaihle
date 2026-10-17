# Production calibration data

One `<rubric_id>.json` per judge rubric: the stored result of a calibration run. Production evaluation
(`app/services/eval_prod/registry.py`) reads this directory (setting `EVAL_CALIBRATION_DIR`, default this
path) to decide which judge rubrics may run on real output. With no files here every rubric is `MISSING`
and only the deterministic checks run.

## What a file contains

Metrics and hashes only: criterion id, subset (`computed` or `authored`), rubric text hash (SHA-256),
status, three rates (`recall`, `false_alarm`, `indeterminate`: numerator, denominator, point, Wilson
low/high), cross-talk counts keyed by defect label, and a UTC timestamp. No question text, no prompt, no
response, no model name. The promotion command refuses any file with another field or a non-identifier string.

## How files get here

1. Run the live calibration (`evals/calibration_run.py`, see `docs/eval/RUNNING_EVALS.md`); it writes to the
   gitignored `backend/evals/reports/calibration/`.
2. From `backend/`, preview then promote:

       uv run python -m app.services.eval_prod.promote_calibration --dry-run
       uv run python -m app.services.eval_prod.promote_calibration

   Stale (rubric text changed since the run), malformed, unknown-rubric and unexpected-field files are
   refused or skipped with the reason printed. Exit code 1 means at least one file was refused.
3. Review the diff and commit the JSON files. Rewording a rubric changes its hash and makes its file
   `STALE` (the rubric stops running) until calibration is re-run and re-promoted.
