"""Promote stored calibration results into the tracked production directory (MLH-T18).

The offline harness writes calibration files to ``backend/evals/reports/calibration`` (gitignored, so
absent from the image). Production reads ``EVAL_CALIBRATION_DIR`` (default: the tracked
``app/ai/eval/calibration_data``). This command copies a file across only when it is safe to ship:

  * its criterion is a production judge rubric and matches the file name;
  * it has EXACTLY the schema ``save_calibration`` writes (no extra or missing field, at any level);
  * its rubric hash equals the CURRENT ``RubricSpec.text_hash`` (otherwise it is stale);
  * its stored status equals the status recomputed from its rates, and its timestamp parses;
  * every string in it is a short token (ids, enum names, hashes, ISO time), so no question, prompt or
    response text can ride along.

Pure file I/O: no judge, no DeepEval, no database. Run:

    python -m app.services.eval_prod.promote_calibration [--source DIR] [--dest DIR] [--dry-run]

Exit code: 0 all fine (skips allowed), 1 at least one file refused, 2 source directory not found.
"""

import argparse
import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ai.eval.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationResult,
    CalibrationStatus,
    calibration_status,
    load_calibration,
)
from app.ai.eval.grade_rubrics import GRADE_RUBRIC_SPECS
from app.ai.eval.rubric_core import RubricSpec
from app.core.config import settings
from app.services.eval_prod.question_evaluators import QUESTION_RUBRIC_SPECS

# Every judge rubric the production registry can register (test-guarded against `default_registry()`).
PRODUCTION_RUBRIC_SPECS: tuple[RubricSpec, ...] = (*QUESTION_RUBRIC_SPECS, *GRADE_RUBRIC_SPECS)

_TOP_FIELDS = frozenset(
    {"criterion", "subset", "rubric_hash", "status", "recall", "false_alarm", "indeterminate", "crosstalk", "saved_at"}
)
_RATE_FIELDS = frozenset({"numerator", "denominator", "point", "low", "high"})
_RATE_KEYS = ("recall", "false_alarm", "indeterminate")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")


@dataclass(frozen=True)
class PromotionOutcome:
    file_name: str
    promoted: bool
    reason: str
    refused: bool = False  # True for a defect (stale, malformed...), False for a plain skip


def _schema_problem(data: object) -> str | None:
    if not isinstance(data, dict):
        return "malformed: top level is not an object"
    keys = set(data)
    if keys != _TOP_FIELDS:
        extra, missing = sorted(keys - _TOP_FIELDS), sorted(_TOP_FIELDS - keys)
        return f"unexpected schema: extra fields {extra}, missing fields {missing}"
    for name in _RATE_KEYS:
        rate_data = data[name]
        if not isinstance(rate_data, dict) or set(rate_data) != _RATE_FIELDS:
            return f"unexpected schema: {name} must have exactly {sorted(_RATE_FIELDS)}"
    crosstalk = data["crosstalk"]
    if not isinstance(crosstalk, dict):
        return "malformed: crosstalk is not an object"
    for token in (data["criterion"], data["subset"], data["rubric_hash"], data["status"], *crosstalk):
        if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
            return "unexpected content: a string field is not a short identifier"
    try:
        datetime.fromisoformat(str(data["saved_at"]))
    except ValueError:
        return "malformed: saved_at is not an ISO timestamp"
    return None


def _file_problem(path: Path, spec: RubricSpec) -> str | None:
    """Why ``path`` must not be promoted for ``spec``, or None when it is safe."""
    try:
        data: Any = json.loads(path.read_text())
    except (OSError, ValueError):
        return "malformed: unreadable or not JSON"
    problem = _schema_problem(data)
    if problem is not None:
        return problem
    if data["criterion"] != spec.id:
        return "malformed: criterion does not match the file name"
    stored = load_calibration(spec.id, spec.text_hash, path.parent)
    if stored is CalibrationStatus.STALE:
        return "stale: rubric hash differs from the current rubric text (re-run calibration)"
    if not isinstance(stored, CalibrationResult):
        return "malformed: values have the wrong types"
    if data["status"] != calibration_status(stored, stored.subset).value:
        return "malformed: stored status does not match its rates"
    return None


def _copy_atomically(source: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dest_dir, prefix=f".{source.stem}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(source.read_bytes())
        os.replace(tmp, dest_dir / source.name)
    finally:
        tmp.unlink(missing_ok=True)


def promote_calibration(
    source: Path,
    dest: Path,
    *,
    specs: Sequence[RubricSpec] = PRODUCTION_RUBRIC_SPECS,
    dry_run: bool = False,
) -> list[PromotionOutcome]:
    """Copy each valid ``*.json`` in ``source`` to ``dest``. Side effect: writes files unless ``dry_run``.

    Raises FileNotFoundError when ``source`` is not a directory.
    """
    if not source.is_dir():
        raise FileNotFoundError(str(source))
    by_id = {spec.id: spec for spec in specs}
    outcomes: list[PromotionOutcome] = []
    for path in sorted(source.glob("*.json")):
        spec = by_id.get(path.stem)
        if spec is None:
            outcomes.append(PromotionOutcome(path.name, False, "skipped: not a production rubric"))
            continue
        problem = _file_problem(path, spec)
        if problem is not None:
            outcomes.append(PromotionOutcome(path.name, False, f"refused: {problem}", refused=True))
            continue
        if not dry_run:
            _copy_atomically(path, dest)
        outcomes.append(PromotionOutcome(path.name, True, "would promote" if dry_run else "promoted"))
    return outcomes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote harness calibration results to the tracked directory.")
    parser.add_argument("--source", type=Path, default=DEFAULT_CALIBRATION_DIR, help="harness output directory")
    parser.add_argument("--dest", type=Path, default=settings.eval_calibration_dir, help="production directory")
    parser.add_argument("--dry-run", action="store_true", help="validate and report; copy nothing")
    args = parser.parse_args(argv)
    try:
        outcomes = promote_calibration(args.source, args.dest, dry_run=args.dry_run)
    except FileNotFoundError:
        print(f"Source directory not found: {args.source}")
        return 2
    for outcome in outcomes:
        print(f"{outcome.file_name}: {outcome.reason}")
    promoted = sum(o.promoted for o in outcomes)
    refused = sum(o.refused for o in outcomes)
    print(f"{promoted} promoted, {refused} refused, {len(outcomes) - promoted - refused} skipped (dest: {args.dest})")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
