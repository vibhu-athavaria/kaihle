"""Suite-agnostic calibration scoring and persistence (T10 Step 7; reused by T11-T14, T16, T17).

Pure scoring over ``CalibrationVerdict`` records, plus JSON persistence so later tasks read a
rubric's status instead of re-running calibration. No judge, no DeepEval, no model names.

Conventions:
- ``expected_pass=False`` means the case carries a seeded defect that THIS criterion should catch
  (counts towards recall). ``expected_pass=True`` means the criterion should pass (clean case or a
  sampled must-pass check; counts towards false alarm).
- ``observed_pass=None`` is indeterminate: never a pass, excluded from recall/false-alarm
  denominators, reported on its own ``indeterminate`` rate (SD-5).
- One ``CalibrationResult`` covers ONE criterion and ONE subset. Call ``score_calibration`` once
  per criterion per subset (filter the verdict list first); it raises on mixed input.
"""

import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import structlog

from app.ai.eval.thresholds import FALSE_ALARM_UPPER_MAX, MIN_N, RECALL_LOWER_MIN
from app.ai.eval_metrics import Rate, rate

Subset = Literal["computed", "authored"]

# Default location (unchanged by the move out of backend/evals): `backend/evals/reports/calibration`, with
# `backend/` being four levels up from this file. Ignored via `backend/evals/reports/` in .gitignore, added
# by T9 slice 5; tests always pass tmp_path. Production callers pass an explicit directory.
DEFAULT_CALIBRATION_DIR = Path(__file__).resolve().parents[3] / "evals" / "reports" / "calibration"
logger = structlog.get_logger()
_SAFE_CRITERION_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class CalibrationStatus(StrEnum):
    """SD-6 vocabulary (T16 adds the human-validation statuses on top)."""

    CALIBRATED = "CALIBRATED"
    NOT_CALIBRATED = "NOT_CALIBRATED"
    INSUFFICIENT_N = "INSUFFICIENT_N"
    INDICATIVE = "INDICATIVE"
    STALE = "STALE"  # loader marker: stored result was computed under a different rubric hash
    MISSING = "MISSING"  # loader marker: no stored result


@dataclass(frozen=True)
class CalibrationVerdict:
    case_id: str
    criterion: str  # a RubricSpec.id or a deterministic-check name
    defect: str | None  # the seeded defect this case carries, or None for a clean case
    expected_pass: bool  # ground truth for THIS criterion on THIS case
    observed_pass: bool | None  # None = indeterminate (never a pass)
    subset: Subset


@dataclass(frozen=True)
class CalibrationResult:
    criterion: str
    subset: Subset
    rubric_hash: str
    recall: Rate  # seeded defects targeting this criterion that it failed
    false_alarm: Rate  # expected-pass cases that it failed
    indeterminate: Rate  # all verdicts for the criterion that were indeterminate
    # defect -> fails observed on cases where this criterion should have PASSED (defect targets another one)
    crosstalk: dict[str, int]


def score_calibration(verdicts: Iterable[CalibrationVerdict], rubric_hash: str) -> CalibrationResult:
    """Score one criterion's verdicts. ``rubric_hash`` is ``RubricSpec.text_hash`` (or a check's id)."""
    items = list(verdicts)
    if not items:
        raise ValueError("score_calibration needs at least one verdict")
    criterion, subset = items[0].criterion, items[0].subset
    if any(v.criterion != criterion for v in items):
        raise ValueError("score_calibration scores one criterion at a time; verdicts mix criterion values")
    if any(v.subset != subset for v in items):
        raise ValueError("score_calibration scores one subset at a time; verdicts mix subset values")

    determinate = [v for v in items if v.observed_pass is not None]
    defects = [v for v in determinate if not v.expected_pass]
    should_pass = [v for v in determinate if v.expected_pass]
    crosstalk: dict[str, int] = {}
    for v in should_pass:
        if v.defect is not None and v.observed_pass is False:
            crosstalk[v.defect] = crosstalk.get(v.defect, 0) + 1

    return CalibrationResult(
        criterion=criterion,
        subset=subset,
        rubric_hash=rubric_hash,
        recall=rate(sum(v.observed_pass is False for v in defects), len(defects)),
        false_alarm=rate(sum(v.observed_pass is False for v in should_pass), len(should_pass)),
        indeterminate=rate(len(items) - len(determinate), len(items)),
        crosstalk=crosstalk,
    )


def crosstalk_matrix(results: Mapping[str, CalibrationResult]) -> dict[str, dict[str, int]]:
    """defect -> criterion -> cross-talk fail count, assembled from per-criterion results."""
    matrix: dict[str, dict[str, int]] = {}
    for criterion, result in results.items():
        for defect, count in result.crosstalk.items():
            matrix.setdefault(defect, {})[criterion] = count
    return matrix


def calibration_status(result: CalibrationResult, subset: Subset) -> CalibrationStatus:
    """Apply the pre-registered thresholds. The authored subset is capped at INDICATIVE (SD-6)."""
    if result.recall.denominator < MIN_N or result.false_alarm.denominator < MIN_N:
        return CalibrationStatus.INSUFFICIENT_N
    if result.recall.low < RECALL_LOWER_MIN or result.false_alarm.high > FALSE_ALARM_UPPER_MAX:
        return CalibrationStatus.NOT_CALIBRATED
    return CalibrationStatus.CALIBRATED if subset == "computed" else CalibrationStatus.INDICATIVE


def _path_for(criterion: str, directory: Path) -> Path:
    if not _SAFE_CRITERION_RE.fullmatch(criterion):
        raise ValueError(f"unsafe criterion name for a file path: {criterion!r}")
    return directory / f"{criterion}.json"


def _rate_to_dict(r: Rate) -> dict[str, int | float]:
    return {"numerator": r.numerator, "denominator": r.denominator, "point": r.point, "low": r.low, "high": r.high}


def _int_field(value: object) -> int:
    """Plain int only: bool and float are rejected, never coerced."""
    if type(value) is not int:
        raise TypeError("expected an int")
    return value


def _float_field(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("expected a number")
    return float(value)


def _rate_from_dict(data: object) -> Rate:
    if not isinstance(data, dict):
        raise TypeError("rate must be an object")
    return Rate(
        numerator=_int_field(data["numerator"]),
        denominator=_int_field(data["denominator"]),
        point=_float_field(data["point"]),
        low=_float_field(data["low"]),
        high=_float_field(data["high"]),
    )


def _result_from_dict(data: dict[str, Any], criterion: str) -> CalibrationResult:
    """Build a result from stored data; raises KeyError/TypeError/ValueError on any defect."""
    if data["criterion"] != criterion:
        raise ValueError("stored criterion does not match the requested one")
    if data["subset"] not in ("computed", "authored"):
        raise ValueError("unknown subset")
    stored_crosstalk = data["crosstalk"]
    if not isinstance(stored_crosstalk, dict):
        raise TypeError("crosstalk must be an object")
    return CalibrationResult(
        criterion=criterion,
        subset=data["subset"],
        rubric_hash=data["rubric_hash"],
        recall=_rate_from_dict(data["recall"]),
        false_alarm=_rate_from_dict(data["false_alarm"]),
        indeterminate=_rate_from_dict(data["indeterminate"]),
        crosstalk={str(k): _int_field(v) for k, v in stored_crosstalk.items()},
    )


def save_calibration(result: CalibrationResult, directory: Path = DEFAULT_CALIBRATION_DIR) -> Path:
    """Write ``<criterion>.json`` atomically (hash, rates, status, UTC time; no model names).

    Side effect: file I/O. Writes a temp file in the same directory then ``os.replace``s it, so a
    crash mid-write cannot leave a partial file; the temp file is removed on failure.
    """
    path = _path_for(result.criterion, directory)
    payload = {
        "criterion": result.criterion,
        "subset": result.subset,
        "rubric_hash": result.rubric_hash,
        "status": calibration_status(result, result.subset).value,
        "recall": _rate_to_dict(result.recall),
        "false_alarm": _rate_to_dict(result.false_alarm),
        "indeterminate": _rate_to_dict(result.indeterminate),
        "crosstalk": result.crosstalk,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{result.criterion}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)  # no-op after a successful replace
    return path


def load_calibration(
    criterion: str, rubric_hash: str, directory: Path = DEFAULT_CALIBRATION_DIR
) -> CalibrationResult | CalibrationStatus:
    """Stored result, ``STALE`` (valid file, different rubric hash) or ``MISSING`` (no usable calibration).

    Never raises for stored-data defects: an unreadable, non-JSON, non-object, incomplete or wrongly
    typed file (including non-int crosstalk counts) is ``MISSING`` and logs a
    ``calibration_file_unreadable`` warning with the path and exception class, never the content.
    The hash is checked first, so a file for another rubric version is ``STALE`` even if the rest of
    it is damaged. An unsafe ``criterion`` name is a caller error and still raises ``ValueError``.
    """
    path = _path_for(criterion, directory)
    if not path.is_file():
        return CalibrationStatus.MISSING
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise TypeError("top level must be an object")
        stored_hash = data["rubric_hash"]
        if not isinstance(stored_hash, str):
            raise TypeError("rubric_hash must be a string")
        if stored_hash != rubric_hash:
            return CalibrationStatus.STALE
        return _result_from_dict(data, criterion)
    except (OSError, ValueError, KeyError, TypeError) as exc:  # ValueError covers JSON and Unicode decode errors
        logger.warning("calibration_file_unreadable", path=str(path), reason=type(exc).__name__)
        return CalibrationStatus.MISSING
