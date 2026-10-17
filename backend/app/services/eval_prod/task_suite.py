"""The per-task seam of the production run service (MLH-T18 slice 5c).

A `TaskSuite` is everything the runner needs to know about ONE router task, so the runner itself is
task-agnostic:

* ``prepare``: stored event -> `PreparedRow` (or `UnsupportedRow`, counted by the runner). This is the
  only place text is parsed or scrubbed.
* ``deterministic``: run one named deterministic check on the row's STORED form.
* ``rubric_applies`` / ``run_rubric``: decide per row whether a judge rubric is meaningful, and run it
  on the row's SCRUBBED form.

Two forms of a row, on purpose. ``stored`` is what the deterministic checks read (they run locally and
scrub tokens would distort them). ``scrubbed`` is the ONLY form a judge ever sees. The runner passes a
`ScrubContext` to ``prepare`` only when a judge rubric will run; with ``scrub=None`` a suite must not
scrub (nor need to parse text the deterministic checks do not use) and returns ``scrubbed=None``.
``prepare`` raises `ScrubFailedError` when scrubbing cannot be confirmed: the runner skips and counts
the row, so unscrubbed text never reaches the judge.

Nothing here stores or logs text.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.ai.eval.judge_runner import Completion
from app.ai.eval.rubric_core import RubricSpec
from app.services.eval_prod.sampler import SampledEvent


@dataclass(frozen=True)
class ScrubContext:
    """Names to mask in a row's text (the row's school's people and the school itself)."""

    person_names: tuple[str, ...]
    school_name: str | None


@dataclass(frozen=True)
class PreparedRow[Stored, Scrubbed]:
    stored: Stored
    scrubbed: Scrubbed | None  # None when no scrubbing was requested (no judge rubric will run)


@dataclass(frozen=True)
class UnsupportedRow:
    reason: str  # a short code, safe to log and tally; never text from the row


@dataclass(frozen=True)
class TaskSuite[Stored, Scrubbed]:
    prepare: Callable[[SampledEvent, str, ScrubContext | None], PreparedRow[Stored, Scrubbed] | UnsupportedRow]
    # True/False, or None when the check is not computable for this row (no outcome is recorded).
    deterministic: Callable[[str, Stored], bool | None]
    rubric_applies: Callable[[RubricSpec, Scrubbed], bool]
    run_rubric: Callable[[RubricSpec, Scrubbed, Completion], Awaitable[bool | None]]
