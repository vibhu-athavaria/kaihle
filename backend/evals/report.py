"""Markdown report helpers and the grade_open_answer report (T9).

Shared helpers (``rate_line``, ``caveat_block``, ``markdown_table``) are reusable by later suites; each
later suite owns its OWN report module and must not edit this one's grading renderer.
Reports are written to a gitignored directory because they record resolved model strings (SD-2, SD-14).
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import structlog

from app.ai.eval_metrics import Rate, rate
from app.ai.providers.router import TASK_MODEL_MAP
from app.core.config import settings
from evals.grade_metrics import GradeSummary, render_confusion_matrix
from evals.judge import JUDGE_TASK

logger = structlog.get_logger()

GRADED_TASK = "grade_open_answer"
DEFAULT_REPORT_DIR = Path(__file__).resolve().parent / "reports"
# Human-readable ISO-8601 UTC for the report body; the filename variant avoids ':' (invalid on some filesystems).
REPORT_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FILENAME_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"
UNSET_MODEL = "(unset)"
_UNSAFE_FILENAME_CHARS = re.compile(r"[:/\\]")

LABEL_CAVEAT = (
    "Labels in the golden dataset are model-authored and unvalidated by a human. Every figure below "
    "measures agreement with those labels, not verified correctness. Do not quote any number here as a "
    "verified accuracy."
)
VARIANCE_NOTE = "Single run, temperature=0; judge variance not measured."


@dataclass(frozen=True)
class RubricResult:
    """G-Eval outcome for one rubric. ``errors`` (indeterminate judge replies) are excluded from n."""

    name: str
    passes: int
    evaluated: int
    errors: int = 0


@dataclass(frozen=True)
class RunMeta:
    timestamp_utc: str
    judge_model: str
    graded_model: str
    dataset_sha256: str
    deepeval_version: str


def rate_line(label: str, value: Rate) -> str:
    """One bullet; ``Rate.format()`` guarantees the sample size is shown."""
    return f"- {label}: {value.format()}"


def caveat_block(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.splitlines())


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime(FILENAME_TIMESTAMP_FORMAT)


def build_run_meta(dataset_path: Path) -> RunMeta:
    """Resolve model strings from settings AT RUN TIME; they are never cached or hardcoded.

    An unconfigured model renders as ``(unset)`` with a WARNING rather than an empty header, which
    would read like a measurement of nothing. Offline report tests legitimately have no config.
    """
    judge = TASK_MODEL_MAP.get(JUDGE_TASK) or settings.llm_eval_judge_model
    graded = TASK_MODEL_MAP.get(GRADED_TASK, "")
    if not judge or not graded:
        logger.warning("eval_report_model_unset", judge_set=bool(judge), graded_set=bool(graded))
    return RunMeta(
        timestamp_utc=datetime.now(UTC).strftime(REPORT_TIMESTAMP_FORMAT),
        judge_model=judge or UNSET_MODEL,
        graded_model=graded or UNSET_MODEL,
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        deepeval_version=version("deepeval"),
    )


def _safe_timestamp(timestamp: str) -> str:
    """Make a caller-supplied timestamp filename-safe; reject traversal."""
    if ".." in timestamp:
        raise ValueError(f"timestamp must not contain '..': {timestamp!r}")
    return _UNSAFE_FILENAME_CHARS.sub("-", timestamp)


def _rubric_rows(results: Sequence[RubricResult]) -> list[list[str]]:
    return [[r.name, rate(r.passes, r.evaluated).format(), str(r.errors)] for r in results]


def render_report(summary: GradeSummary, run_meta: RunMeta, rubric_results: Sequence[RubricResult] = ()) -> str:
    """Render the report. Order is fixed: caveat first, then metrics, then G-Eval, then run metadata."""
    parts = [
        "# grade_open_answer evaluation",
        caveat_block(LABEL_CAVEAT),
        "## Accuracy\n"
        + rate_line("Accuracy (cases with a parseable reply)", summary.accuracy)
        + "\n"
        + rate_line("Unrecognised-grade rate (valid JSON, unknown grade)", summary.unrecognised_grade_rate),
        "## Confusion matrix\n" + render_confusion_matrix(summary.confusion),
        "## False credit\n"
        + "Expected incorrect, graded correct. Inflates mastery and hides the gap Kaihle exists to find.\n"
        + rate_line("False-credit rate", summary.false_credit_rate),
        "## False denial\n"
        + "Expected correct, graded incorrect. Reported separately: the harm is discouragement.\n"
        + rate_line("False-denial rate", summary.false_denial_rate),
        "## Parse failure\n"
        + "Unparseable replies are silently stored as incorrect in production. Not folded into accuracy.\n"
        + rate_line("Parse-failure rate (all cases)", summary.parse_failure_rate),
        "## Accuracy by tag\n"
        + (
            markdown_table(["tag", "accuracy"], [[t, r.format()] for t, r in sorted(summary.per_tag_accuracy.items())])
            if summary.per_tag_accuracy
            else "No tagged cases."
        ),
        "## G-Eval feedback rubrics\n"
        + (
            markdown_table(["rubric", "pass rate", "indeterminate"], _rubric_rows(rubric_results))
            + "\n\n"
            + VARIANCE_NOTE
            if rubric_results
            else "G-Eval rubrics were not run."
        ),
        "## Run metadata\n"
        + "\n".join(
            [
                f"- Timestamp (UTC): {run_meta.timestamp_utc}",
                f"- Judge model: {run_meta.judge_model}",
                f"- Graded model: {run_meta.graded_model}",
                f"- Dataset SHA-256: {run_meta.dataset_sha256}",
                f"- DeepEval version: {run_meta.deepeval_version}",
                f"- Cases: {summary.total}",
            ]
        ),
    ]
    return "\n\n".join(parts) + "\n"


def write_report(content: str, out_dir: Path | None = None, timestamp_utc: str | None = None) -> Path:
    """Write the report; the default directory is gitignored. Returns the path written."""
    directory = out_dir or DEFAULT_REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{GRADED_TASK}_{_safe_timestamp(timestamp_utc) if timestamp_utc else utc_timestamp()}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("eval_report_written", path=str(path), bytes=len(content))
    return path
