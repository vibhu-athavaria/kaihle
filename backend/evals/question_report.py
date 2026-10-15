"""Markdown reports for the question-quality suite (T10 Step 10). Owns only question-suite rendering.

Shared helpers (rate formatting, caveat blocks, tables) come from ``evals.report``. Reports go to the
gitignored ``evals/reports`` directory.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from app.ai.eval_metrics import Rate
from evals.calibration import CalibrationResult, CalibrationStatus, calibration_status, crosstalk_matrix
from evals.judge import JUDGE_MODEL_LABEL
from evals.report import DEFAULT_REPORT_DIR, caveat_block, markdown_table, rate_line

logger = structlog.get_logger()

CALIBRATION_CAVEAT = (
    "Synthetic defects are easier to detect than natural ones, so recall here is an upper bound. "
    "Seeded-defect calibration does not measure judgement on genuinely ambiguous questions; it measures "
    "detection of known, code-computed defects. Statuses use the pre-registered thresholds in "
    "evals/thresholds.py. Indeterminate judge replies are never counted as passes."
)
GENERATION_CAVEAT = (
    "Quality figures are report-only (no gate). Deterministic checks run on every MCQ; judge rubrics run on "
    "a seeded sample, so their n is smaller. A rubric whose calibration is anything other than CALIBRATED is "
    "indicative only."
)
F1_NOTE = (
    "F1: the practice-quiz path appears to run without subject name or interests in production (the Subtopic "
    "model carries neither). This eval supplies the INTENDED context, so every figure here is an upper bound "
    "on what students currently receive from this path."
)
UNCALIBRATED_BANNER = "UNCALIBRATED — indicative only"
_HEADERS = ("Criterion", "Recall", "False alarm", "Indeterminate", "Status")


def _rows(results: Mapping[str, CalibrationResult]) -> list[list[str]]:
    return [
        [
            criterion,
            r.recall.format(),
            r.false_alarm.format(),
            r.indeterminate.format(),
            calibration_status(r, r.subset).value,
        ]
        for criterion, r in sorted(results.items())
    ]


def _crosstalk_section(results: Mapping[str, CalibrationResult]) -> str:
    matrix = crosstalk_matrix(results)
    if not matrix:
        return "No cross-talk failures observed."
    criteria = sorted({c for row in matrix.values() for c in row})
    rows = [[defect, *(str(matrix[defect].get(c, 0)) for c in criteria)] for defect in sorted(matrix)]
    return markdown_table(("Defect", *criteria), rows)


def render_calibration_report(
    results: Mapping[str, CalibrationResult], prod_results: Mapping[str, CalibrationResult], timestamp_utc: str
) -> str:
    """Rubric table, cross-talk matrix, then the production judge's table on the same questions."""
    prod = (
        markdown_table(_HEADERS, _rows(prod_results)) if prod_results else "Production judge: not run for this report."
    )
    parts = [
        "# Question-quality calibration report",
        f"- Generated: {timestamp_utc}\n- Judge: {JUDGE_MODEL_LABEL}",
        caveat_block(CALIBRATION_CAVEAT),
        "## Rubric calibration\n\n" + markdown_table(_HEADERS, _rows(results)),
        "## Cross-talk (failures on criteria the defect should not affect)\n\n" + _crosstalk_section(results),
        "## Production question_quality judge (same questions, mapped criteria)\n\n" + prod,
    ]
    return "\n\n".join(parts) + "\n"


def _write_report(prefix: str, content: str, out_dir: Path | None, timestamp_utc: str) -> Path:
    if ".." in timestamp_utc or "/" in timestamp_utc:
        raise ValueError(f"unsafe timestamp for a file name: {timestamp_utc!r}")
    directory = out_dir or DEFAULT_REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{prefix}_{timestamp_utc}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("eval_report_written", path=str(path), bytes=len(content))
    return path


def write_calibration_report(content: str, out_dir: Path | None = None, timestamp_utc: str = "") -> Path:
    """Side effect: writes ``question_calibration_<timestamp>.md`` under ``out_dir`` (default is gitignored)."""
    return _write_report("question_calibration", content, out_dir, timestamp_utc)


def write_generation_report(
    content: str, path: Literal["bank", "quiz"], out_dir: Path | None = None, timestamp_utc: str = ""
) -> Path:
    """Side effect: writes ``question_generation_<path>_<timestamp>.md`` under ``out_dir`` (gitignored default)."""
    return _write_report(f"question_generation_{path}", content, out_dir, timestamp_utc)


@dataclass(frozen=True)
class RubricLine:
    """One judge rubric's result on generated questions. ``status`` is a CalibrationStatus value."""

    criterion: str
    pass_rate: Rate  # over determinate verdicts only
    indeterminate: Rate  # over all verdicts; an indeterminate reply is never a pass
    status: str


@dataclass(frozen=True)
class GenerationSummary:
    path: Literal["bank", "quiz"]
    specs: int
    structural: Mapping[str, int]  # per-spec outcome status -> count
    mcq: int
    true_false: int  # set aside: the MCQ rubrics do not apply
    schema_failures: Rate  # MCQs that failed the production schema validator
    deterministic: Mapping[str, Rate]  # check name -> pass rate
    key_counts: Mapping[str, int]
    key_max_share: float
    rubrics: Sequence[RubricLine]
    per_subject: Mapping[str, Rate]  # subject -> share of MCQs passing every deterministic check


def _rubric_row(line: RubricLine) -> list[str]:
    status = line.status
    shown = status if status == CalibrationStatus.CALIBRATED.value else f"{UNCALIBRATED_BANNER} ({status})"
    return [line.criterion, line.pass_rate.format(), line.indeterminate.format(), shown]


def render_generation_report(summary: GenerationSummary, timestamp_utc: str) -> str:
    """Fixed order: caveats, structure, deterministic checks, key letters, judge rubrics, subjects."""
    parts = [
        f"# Question generation report ({summary.path})",
        f"- Generated: {timestamp_utc}\n- Judge: {JUDGE_MODEL_LABEL}",
        caveat_block(GENERATION_CAVEAT + ("\n" + F1_NOTE if summary.path == "quiz" else "")),
        "## Structural outcomes\n"
        + markdown_table(("Outcome", "Specs"), [[k, str(v)] for k, v in sorted(summary.structural.items())])
        + f"\n\n- Specs: {summary.specs}\n- MCQs evaluated: {summary.mcq}\n"
        + f"- True/false questions set aside: {summary.true_false}\n"
        + rate_line("MCQs failing the production schema validator", summary.schema_failures),
        "## Deterministic checks\n"
        + markdown_table(("Check", "Pass rate"), [[k, v.format()] for k, v in sorted(summary.deterministic.items())]),
        "## Answer-key distribution (reported, never gated)\n"
        + ", ".join(f"{k}: {v}" for k, v in sorted(summary.key_counts.items()))
        + f"; largest share {summary.key_max_share:.0%}",
        "## Judge rubrics\n"
        + markdown_table(
            ("Rubric", "Pass rate", "Indeterminate", "Calibration"), [_rubric_row(r) for r in summary.rubrics]
        ),
        "## Per-subject (all deterministic checks passed)\n"
        + markdown_table(("Subject", "Pass rate"), [[k, v.format()] for k, v in sorted(summary.per_subject.items())]),
    ]
    return "\n\n".join(parts) + "\n"
