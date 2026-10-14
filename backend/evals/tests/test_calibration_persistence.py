"""Offline tests for calibration persistence robustness: corrupt files, atomic writes, default-dir guard."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from evals import calibration as calibration_module
from evals.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationStatus,
    CalibrationVerdict,
    load_calibration,
    save_calibration,
    score_calibration,
)

CRIT = "R2_exactly_one_correct"
HASH = "a" * 64


def _stored(tmp_path: Path) -> Path:
    """Save a valid result and return its path, for tests that then damage the file."""
    verdicts = [CalibrationVerdict(f"d{i}", CRIT, "wrong_key", False, i % 5 != 0, "computed") for i in range(25)]
    verdicts += [CalibrationVerdict(f"k{i}", CRIT, None, True, True, "computed") for i in range(25)]
    return save_calibration(score_calibration(verdicts, rubric_hash=HASH), tmp_path)


def _damage(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


@pytest.fixture(autouse=True)
def _forbid_default_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test resolves a file path inside the real default calibration directory."""
    real = calibration_module._path_for

    def guarded(criterion: str, directory: Path) -> Path:
        assert directory != DEFAULT_CALIBRATION_DIR, "test touched the real default calibration directory"
        return real(criterion, directory)

    monkeypatch.setattr(calibration_module, "_path_for", guarded)


def test_calibration_tests_when_run_then_default_directory_is_never_written() -> None:
    result = score_calibration([CalibrationVerdict("a", CRIT, "d", False, False, "computed")], rubric_hash=HASH)

    # The guard fixture is active for every test in this module (and fails them if they touch the real
    # directory); prove it actually trips on a default-directory call.
    with pytest.raises(AssertionError, match="default calibration directory"):
        save_calibration(result)
    with pytest.raises(AssertionError, match="default calibration directory"):
        load_calibration(CRIT, HASH)


def test_load_calibration_when_file_is_not_valid_json_then_returns_missing_and_warns(tmp_path: Path) -> None:
    (tmp_path / f"{CRIT}.json").write_text("not json at all")

    with patch("evals.calibration.logger") as log:
        assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING

    log.warning.assert_called_once()
    assert log.warning.call_args.args[0] == "calibration_file_unreadable"


def test_load_calibration_when_file_is_truncated_then_returns_missing(tmp_path: Path) -> None:
    path = _stored(tmp_path)
    path.write_text(path.read_text()[:60])

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


def test_load_calibration_when_top_level_is_not_an_object_then_returns_missing(tmp_path: Path) -> None:
    (tmp_path / f"{CRIT}.json").write_text("[1, 2, 3]")

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


@pytest.mark.parametrize(
    "key", ["rubric_hash", "criterion", "subset", "recall", "false_alarm", "indeterminate", "crosstalk"]
)
def test_load_calibration_when_required_key_absent_then_returns_missing(tmp_path: Path, key: str) -> None:
    _damage(_stored(tmp_path), lambda d: d.pop(key))

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


@pytest.mark.parametrize(
    "bad",
    [{"numerator": 1}, "x", None, {"numerator": "1", "denominator": 2, "point": 0.5, "low": 0.0, "high": 1.0}],
)
def test_load_calibration_when_rate_dict_malformed_then_returns_missing(tmp_path: Path, bad: object) -> None:
    _damage(_stored(tmp_path), lambda d: d.__setitem__("recall", bad))

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


@pytest.mark.parametrize("bad", [1.5, "2", None, True])
def test_load_calibration_when_crosstalk_value_is_float_string_null_or_bool_then_returns_missing(
    tmp_path: Path, bad: object
) -> None:
    _damage(_stored(tmp_path), lambda d: d.__setitem__("crosstalk", {"wrong_key": bad}))

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


def test_load_calibration_when_hash_differs_and_rest_of_file_corrupt_then_returns_stale(tmp_path: Path) -> None:
    def corrupt(d: dict[str, Any]) -> None:
        d["recall"] = "garbage"
        d.pop("crosstalk")

    _damage(_stored(tmp_path), corrupt)

    assert load_calibration(CRIT, "b" * 64, tmp_path) is CalibrationStatus.STALE


def test_load_calibration_when_file_unreadable_bytes_then_returns_missing(tmp_path: Path) -> None:
    (tmp_path / f"{CRIT}.json").write_bytes(b"\xff\xfe\x00\x80")

    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


def test_load_calibration_when_corrupt_then_warning_has_path_and_reason_but_not_file_content(tmp_path: Path) -> None:
    path = tmp_path / f"{CRIT}.json"
    path.write_text("SECRET-CONTENT-123 {")

    with patch("evals.calibration.logger") as log:
        load_calibration(CRIT, HASH, tmp_path)

    kwargs = log.warning.call_args.kwargs
    assert kwargs["path"] == str(path)
    assert kwargs["reason"] == "JSONDecodeError"
    assert "SECRET-CONTENT-123" not in repr(log.warning.call_args)


def test_save_calibration_when_write_fails_midway_then_existing_file_is_untouched_and_no_temp_file_left(
    tmp_path: Path,
) -> None:
    path = _stored(tmp_path)
    before = path.read_text()
    other = score_calibration([CalibrationVerdict("z", CRIT, "d", False, True, "computed")], rubric_hash="c" * 64)

    with patch("evals.calibration.os.replace", side_effect=OSError("disk full")), pytest.raises(OSError):
        save_calibration(other, tmp_path)

    assert path.read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_save_calibration_when_called_then_leaves_no_temp_files_in_directory(tmp_path: Path) -> None:
    path = _stored(tmp_path)

    assert [p.name for p in tmp_path.iterdir()] == [path.name]
