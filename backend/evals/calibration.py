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
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from app.ai.eval_metrics import Rate, rate
from evals.thresholds import FALSE_ALARM_UPPER_MAX, MIN_N, RECALL_LOWER_MIN

Subset = Literal["computed", "authored"]

# Default location; gitignored by T9 slice 5. Tests always pass tmp_path.
DEFAULT_CALIBRATION_DIR = Path(__file__).resolve().parent / "reports" / "calibration"
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


def _rate_from_dict(data: Mapping[str, int | float]) -> Rate:
    return Rate(
        numerator=int(data["numerator"]),
        denominator=int(data["denominator"]),
        point=float(data["point"]),
        low=float(data["low"]),
        high=float(data["high"]),
    )


def save_calibration(result: CalibrationResult, directory: Path = DEFAULT_CALIBRATION_DIR) -> Path:
    """Write ``<criterion>.json`` (hash, rates, status, UTC time; no model names). Side effect: file I/O."""
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_calibration(
    criterion: str, rubric_hash: str, directory: Path = DEFAULT_CALIBRATION_DIR
) -> CalibrationResult | CalibrationStatus:
    """Stored result, ``STALE`` if computed under a different rubric hash, ``MISSING`` if no file."""
    path = _path_for(criterion, directory)
    if not path.is_file():
        return CalibrationStatus.MISSING
    data = json.loads(path.read_text())
    if data["rubric_hash"] != rubric_hash:
        return CalibrationStatus.STALE
    return CalibrationResult(
        criterion=data["criterion"],
        subset=data["subset"],
        rubric_hash=data["rubric_hash"],
        recall=_rate_from_dict(data["recall"]),
        false_alarm=_rate_from_dict(data["false_alarm"]),
        indeterminate=_rate_from_dict(data["indeterminate"]),
        crosstalk={str(k): int(v) for k, v in data["crosstalk"].items()},
    )
