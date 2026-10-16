"""Evaluator registry for production evaluation (MLH-T18 slice 4, decisions D4-D6, D14).

Answers, per router task: can it be evaluated, which checks and rubrics apply, does it carry
student text, and which rubrics are trustworthy enough to run on real output.

  * Deterministic checks always run.
  * A judge rubric runs only when its calibration status for the CURRENT rubric hash is
    CALIBRATED or HUMAN_VALIDATED. INDICATIVE rubrics run only when the admin ticked "include
    indicative" and are then marked `indicative`. STALE, MISSING, NOT_CALIBRATED and
    INSUFFICIENT_N never run.
  * Independence is enforced per sampled row against that row's own model (`filter_independent`).

THE REGISTRY STARTS EMPTY (D14). A suite registers its evaluators when it lands. The existing
rubrics and checks live in the offline `evals/` package, which production code cannot import
(DeepEval); moving the DeepEval-free `RubricSpec` definitions into `app/ai/eval/` is a
prerequisite for registering them and belongs to the slice that wires the runner.

Calibration status is resolved through an injectable callable. HUMAN_VALIDATED (T16) is trusted
here already, but the default file-backed resolver cannot produce it until T16 lands.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from app.ai.eval.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationStatus,
    calibration_status,
    load_calibration,
)
from app.ai.eval.judge_guards import RowIndependence, require_judge_configured, row_independence
from app.ai.eval.rubric_core import RubricSpec
from app.services.eval_prod.sampler import SampledEvent
from app.services.platform_settings_service import TASKS_WITH_STUDENT_TEXT, EvalSettings

KIND_DETERMINISTIC = "deterministic"
KIND_JUDGE = "judge"
TRUSTED_STATUSES = frozenset({"CALIBRATED", "HUMAN_VALIDATED"})
INDICATIVE_STATUS = "INDICATIVE"

StatusResolver = Callable[[RubricSpec], str]


@dataclass(frozen=True)
class Evaluator:
    """One check or rubric applicable to a task. Judge evaluators carry their `RubricSpec`."""

    name: str  # becomes eval_results.check_name
    kind: str
    rubric: RubricSpec | None = None

    def __post_init__(self) -> None:
        if self.kind not in (KIND_DETERMINISTIC, KIND_JUDGE):
            raise ValueError(f"unknown evaluator kind {self.kind!r}")
        if (self.kind == KIND_JUDGE) != (self.rubric is not None):
            raise ValueError("judge evaluators need a rubric and deterministic checks must not have one")


@dataclass(frozen=True)
class SelectedEvaluator:
    evaluator: Evaluator
    rubric_hash: str | None  # None for deterministic checks
    rubric_status: str | None
    indicative: bool


@dataclass(frozen=True)
class ExcludedEvaluator:
    evaluator: Evaluator
    rubric_status: str  # why it was left out; shown to the admin


@dataclass(frozen=True)
class EvaluatorPlan:
    supported: bool  # False when nothing is registered for the task (rows count as unsupported)
    selected: tuple[SelectedEvaluator, ...]
    excluded: tuple[ExcludedEvaluator, ...]


@dataclass(frozen=True)
class IndependenceSplit:
    kept: tuple[SampledEvent, ...]
    skipped_not_independent: int


def calibration_status_from_files(spec: RubricSpec, directory: Path = DEFAULT_CALIBRATION_DIR) -> str:
    """Status of ``spec`` for its CURRENT hash from the stored calibration files (reads files)."""
    stored = load_calibration(spec.id, spec.text_hash, directory)
    if isinstance(stored, CalibrationStatus):
        return stored.value  # STALE or MISSING
    return calibration_status(stored, stored.subset).value


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._by_task: dict[str, list[Evaluator]] = defaultdict(list)

    def register(self, task: str, evaluator: Evaluator) -> None:
        if any(existing.name == evaluator.name for existing in self._by_task[task]):
            raise ValueError(f"evaluator {evaluator.name!r} is already registered for task {task!r}")
        self._by_task[task].append(evaluator)

    def supports(self, task: str) -> bool:
        return bool(self._by_task.get(task))

    @staticmethod
    def contains_student_text(task: str) -> bool:
        """Single source: the flag set owned by the platform settings service (acknowledgement gate)."""
        return task in TASKS_WITH_STUDENT_TEXT

    def plan_for(self, task: str, *, include_indicative: bool, status_of: StatusResolver) -> EvaluatorPlan:
        evaluators = self._by_task.get(task, [])
        selected: list[SelectedEvaluator] = []
        excluded: list[ExcludedEvaluator] = []
        for evaluator in evaluators:
            if evaluator.rubric is None:
                selected.append(SelectedEvaluator(evaluator, None, None, indicative=False))
                continue
            status = status_of(evaluator.rubric)
            indicative = status == INDICATIVE_STATUS
            if status in TRUSTED_STATUSES or (indicative and include_indicative):
                selected.append(SelectedEvaluator(evaluator, evaluator.rubric.text_hash, status, indicative=indicative))
            else:
                excluded.append(ExcludedEvaluator(evaluator, status))
        return EvaluatorPlan(supported=bool(evaluators), selected=tuple(selected), excluded=tuple(excluded))


def task_enablement_problem(task: str, settings: EvalSettings) -> str | None:
    """Why ``task`` may not be evaluated under the admin's settings, or None (D5)."""
    if task not in settings.enabled_tasks:
        return f"task {task!r} is not enabled for evaluation"
    if EvaluatorRegistry.contains_student_text(task) and task not in settings.student_text_ack:
        return f"task {task!r} contains student text and has no recorded acknowledgement"
    return None


def filter_independent(events: Iterable[SampledEvent], judge_model: str) -> IndependenceSplit:
    """Keep rows the judge may grade; count the rest (D4).

    Each row is checked against ITS OWN `model` (what generated it, possibly since replaced), not
    today's task map. Same-model, same-vendor and unknown-model rows are skipped. Raises
    JudgeNotConfiguredError when no judge is configured.
    """
    require_judge_configured(judge_model)
    kept: list[SampledEvent] = []
    skipped = 0
    for event in events:
        if row_independence(judge_model, event.model) is RowIndependence.INDEPENDENT:
            kept.append(event)
        else:
            skipped += 1
    return IndependenceSplit(kept=tuple(kept), skipped_not_independent=skipped)
