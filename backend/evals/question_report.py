"""Markdown reports for the question-quality suite (T10 Step 10). Owns only question-suite rendering.

Shared helpers (rate formatting, caveat blocks, tables) come from ``evals.report``. Reports go to the
gitignored ``evals/reports`` directory.
"""

from collections.abc import Mapping
from pathlib import Path

import structlog

from evals.calibration import CalibrationResult, calibration_status, crosstalk_matrix
from evals.judge import JUDGE_MODEL_LABEL
from evals.report import DEFAULT_REPORT_DIR, caveat_block, markdown_table

logger = structlog.get_logger()

CALIBRATION_CAVEAT = (
    "Synthetic defects are easier to detect than natural ones, so recall here is an upper bound. "
    "Seeded-defect calibration does not measure judgement on genuinely ambiguous questions; it measures "
    "detection of known, code-computed defects. Statuses use the pre-registered thresholds in "
    "evals/thresholds.py. Indeterminate judge replies are never counted as passes."
)
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


def write_calibration_report(content: str, out_dir: Path | None = None, timestamp_utc: str = "") -> Path:
    """Side effect: writes ``question_calibration_<timestamp>.md`` under ``out_dir`` (default is gitignored)."""
    if ".." in timestamp_utc or "/" in timestamp_utc:
        raise ValueError(f"unsafe timestamp for a file name: {timestamp_utc!r}")
    directory = out_dir or DEFAULT_REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"question_calibration_{timestamp_utc}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("eval_report_written", path=str(path), bytes=len(content))
    return path
