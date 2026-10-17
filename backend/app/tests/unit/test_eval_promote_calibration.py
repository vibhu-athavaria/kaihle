"""Promotion of stored calibration results into the tracked production directory (MLH-T18).

Pure file I/O: no judge, no DeepEval, no network. Specs are injected so each test controls the
"current" rubric hash.
"""

import json
import re
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval.calibration import PRODUCTION_CALIBRATION_DIR, CalibrationResult, save_calibration
from app.ai.eval.rubric_core import RubricSpec
from app.ai.eval_metrics import rate
from app.core.config import Settings, settings
from app.services.eval_prod.promote_calibration import PRODUCTION_RUBRIC_SPECS, main, promote_calibration
from app.services.eval_prod.question_evaluators import default_registry
from app.services.eval_prod.registry import calibration_status_resolver
from app.services.eval_run_service import EvalRunService

RUBRIC = RubricSpec("R1_test", "Is it fine?", "Judge strictly.", ("stem",))
OTHER = RubricSpec("R2_other", "Is it good?", "Judge kindly.", ("stem",))
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:+-]+$")  # ids, enums, hashes, ISO timestamps: never prose


def _result(
    spec: RubricSpec, *, subset: Literal["computed", "authored"] = "computed", rubric_hash: str | None = None
) -> CalibrationResult:
    return CalibrationResult(
        criterion=spec.id,
        subset=subset,
        rubric_hash=rubric_hash or spec.text_hash,
        recall=rate(60, 60),
        false_alarm=rate(0, 60),
        indeterminate=rate(0, 60),
        crosstalk={"wrong_key": 2},
    )


def _write(source: Path, spec: RubricSpec, **kwargs: Any) -> Path:
    return save_calibration(_result(spec, **kwargs), source)


def _tamper(path: Path, mutate: Any) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


def _outcome(outcomes: list[Any], name: str) -> Any:
    return next(o for o in outcomes if o.file_name == name)


def test_promote_calibration_when_file_valid_then_copied_unchanged(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    written = _write(source, RUBRIC)

    outcomes = promote_calibration(source, dest, specs=(RUBRIC,))

    assert [(o.file_name, o.promoted) for o in outcomes] == [(written.name, True)]
    assert (dest / written.name).read_bytes() == written.read_bytes()


def test_promote_calibration_when_authored_subset_then_copied(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    _write(source, RUBRIC, subset="authored")
    assert promote_calibration(source, dest, specs=(RUBRIC,))[0].promoted


def test_promote_calibration_when_rubric_hash_stale_then_refused(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    written = _write(source, RUBRIC, rubric_hash="0" * 64)

    outcome = promote_calibration(source, dest, specs=(RUBRIC,))[0]

    assert not outcome.promoted
    assert "stale" in outcome.reason.lower()
    assert not (dest / written.name).exists()


@pytest.mark.parametrize("content", ["not json {", "[1, 2]", '{"criterion": "R1_test"}', ""])
def test_promote_calibration_when_content_malformed_then_refused(tmp_path: Path, content: str) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    (source / f"{RUBRIC.id}.json").write_text(content)

    outcome = promote_calibration(source, dest, specs=(RUBRIC,))[0]

    assert not outcome.promoted
    assert not dest.exists() or not list(dest.iterdir())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(prompt_text="What is 2+2?"),
        lambda d: d["recall"].update(note="free text"),
        lambda d: d.pop("saved_at"),
        lambda d: d.update(crosstalk={"a prose sentence about a question": 1}),
        lambda d: d.update(status="CALIBRATED" if d["status"] != "CALIBRATED" else "INDICATIVE"),
        lambda d: d.update(saved_at="not a timestamp"),
    ],
    ids=["extra_top_field", "extra_rate_field", "missing_field", "text_crosstalk_key", "tampered_status", "bad_time"],
)
def test_promote_calibration_when_schema_violated_then_refused(tmp_path: Path, mutate: Any) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    path = _write(source, RUBRIC)
    _tamper(path, mutate)

    outcome = promote_calibration(source, dest, specs=(RUBRIC,))[0]

    assert not outcome.promoted
    assert not (dest / path.name).exists()


def test_promote_calibration_when_criterion_differs_from_filename_then_refused(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    path = _write(source, RUBRIC)
    path.rename(source / f"{OTHER.id}.json")

    outcome = promote_calibration(source, dest, specs=(RUBRIC, OTHER))[0]

    assert not outcome.promoted


def test_promote_calibration_when_criterion_is_not_a_production_rubric_then_skipped(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    _write(source, OTHER)

    outcome = promote_calibration(source, dest, specs=(RUBRIC,))[0]

    assert not outcome.promoted
    assert "not a production rubric" in outcome.reason
    assert not dest.exists() or not list(dest.iterdir())


def test_promote_calibration_when_mixed_files_then_only_valid_ones_copied(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    good = _write(source, RUBRIC)
    bad = _write(source, OTHER, rubric_hash="f" * 64)
    (source / "README.md").write_text("ignored")

    outcomes = promote_calibration(source, dest, specs=(RUBRIC, OTHER))

    assert _outcome(outcomes, good.name).promoted
    assert not _outcome(outcomes, bad.name).promoted
    assert sorted(p.name for p in dest.iterdir()) == [good.name]


def test_promote_calibration_when_dry_run_then_nothing_written(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    _write(source, RUBRIC)

    outcomes = promote_calibration(source, dest, specs=(RUBRIC,), dry_run=True)

    assert outcomes[0].promoted
    assert not dest.exists()


def test_promote_calibration_when_source_missing_then_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        promote_calibration(tmp_path / "nope", tmp_path / "dst", specs=(RUBRIC,))


def test_promoted_artifact_when_inspected_then_holds_no_free_text(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    _write(source, RUBRIC)
    promote_calibration(source, dest, specs=(RUBRIC,))

    def strings(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [s for k, v in node.items() for s in [k, *strings(v)]]
        return [node] if isinstance(node, str) else []

    data = json.loads((dest / f"{RUBRIC.id}.json").read_text())
    assert all(SAFE_TOKEN.fullmatch(s) for s in strings(data))
    assert RUBRIC.question not in json.dumps(data)
    assert RUBRIC.instructions not in json.dumps(data)


def test_production_rubric_specs_when_compared_with_default_registry_then_cover_every_judge_rubric() -> None:
    registered = {
        e.rubric.id
        for task_evaluators in default_registry()._by_task.values()  # noqa: SLF001
        for e in task_evaluators
        if e.rubric is not None
    }
    assert registered
    assert registered == {s.id for s in PRODUCTION_RUBRIC_SPECS}


def test_main_when_run_then_prints_summary_and_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    good = _write(source, PRODUCTION_RUBRIC_SPECS[0])

    code = main(["--source", str(source), "--dest", str(dest)])

    out = capsys.readouterr().out
    assert code == 0
    assert good.name in out and "promoted" in out.lower()
    assert (dest / good.name).is_file()


def test_main_when_a_file_is_refused_then_exits_one_and_names_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, dest = tmp_path / "src", tmp_path / "dst"
    bad = _write(source, PRODUCTION_RUBRIC_SPECS[0], rubric_hash="1" * 64)

    code = main(["--source", str(source), "--dest", str(dest)])

    out = capsys.readouterr().out
    assert code == 1
    assert bad.name in out and "stale" in out.lower()


def test_main_when_source_missing_then_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--source", str(tmp_path / "nope"), "--dest", str(tmp_path / "dst")])
    assert code == 2
    assert "not found" in capsys.readouterr().out.lower()


def test_settings_when_default_then_calibration_dir_is_the_tracked_directory() -> None:
    assert Settings().eval_calibration_dir == PRODUCTION_CALIBRATION_DIR
    assert PRODUCTION_CALIBRATION_DIR.parts[-4:] == ("app", "ai", "eval", "calibration_data")
    assert (PRODUCTION_CALIBRATION_DIR / "README.md").is_file()


def test_settings_when_env_override_then_calibration_dir_follows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_CALIBRATION_DIR", "/srv/calibration")
    assert Settings().eval_calibration_dir == Path("/srv/calibration")


def test_tracked_directory_when_shipped_then_every_artifact_is_valid_and_current(tmp_path: Path) -> None:
    artifacts = [p for p in PRODUCTION_CALIBRATION_DIR.iterdir() if p.suffix == ".json"]
    outcomes = promote_calibration(PRODUCTION_CALIBRATION_DIR, tmp_path / "dst", dry_run=True)
    assert len(outcomes) == len(artifacts)
    assert all(o.promoted for o in outcomes)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "CALIBRATED"),
        ({"subset": "authored"}, "INDICATIVE"),
        ({"rubric_hash": "0" * 64}, "STALE"),
    ],
    ids=["calibrated", "indicative", "stale"],
)
def test_calibration_status_resolver_when_file_present_then_reports_its_status(
    tmp_path: Path, kwargs: dict[str, Any], expected: str
) -> None:
    _write(tmp_path, RUBRIC, **kwargs)
    assert calibration_status_resolver(tmp_path)(RUBRIC) == expected


def test_calibration_status_resolver_when_directory_empty_then_missing(tmp_path: Path) -> None:
    assert calibration_status_resolver(tmp_path)(RUBRIC) == "MISSING"


def test_calibration_status_resolver_when_directory_absent_then_missing(tmp_path: Path) -> None:
    assert calibration_status_resolver(tmp_path / "does-not-exist")(RUBRIC) == "MISSING"


def test_run_service_when_no_resolver_given_then_status_comes_from_configured_directory(tmp_path: Path) -> None:
    _write(tmp_path, RUBRIC)
    config = settings.model_copy(update={"eval_calibration_dir": tmp_path})
    service = EvalRunService(MagicMock(spec=AsyncSession), config=config)

    assert service._status_of(RUBRIC) == "CALIBRATED"  # noqa: SLF001
    assert service._status_of(OTHER) == "MISSING"  # noqa: SLF001
