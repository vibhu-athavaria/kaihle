"""Meta-evaluation of the PRODUCTION question-quality judge (T10 Step 8).

Runs the production prompt (``build_validation_prompt``) and parameters (``QUALITY_*``) through
``complete(task="question_quality")`` on the calibration questions, maps its per-criterion verdicts
onto the new rubric/check ids, and yields ``CalibrationVerdict``s so ``score_calibration`` scores it
exactly like the new rubrics. Router exceptions propagate. An unparseable reply or a criterion the
judge did not return is indeterminate (``None``), never a pass. ``content_domain`` has no seeded
defect and is not scored.
"""

from collections.abc import Sequence
from typing import Any, Literal

import structlog

from app.ai.providers.router import complete
from app.ai.usage_context import llm_component
from evals.calibration import CalibrationVerdict
from evals.judge import JUDGE_COMPONENT
from evals.question_model import EvalQuestion
from scripts.validate_and_fix_questions import (
    QUALITY_MAX_TOKENS,
    QUALITY_SYSTEM_PROMPT,
    QUALITY_TEMPERATURE,
    ValidationResponseError,
    build_validation_prompt,
    parse_validation_response,
)

logger = structlog.get_logger()

PROD_JUDGE_TASK = "question_quality"
# production criterion -> the calibration criteria it speaks to
CRITERION_MAP: dict[str, tuple[str, ...]] = {
    "factual_accuracy": ("R1_key_correctness", "R2_exactly_one_correct"),
    "difficulty_calibration": ("R5_grade_calibration",),
    "subtopic_alignment": ("R4_objective_alignment",),
    "distractor_quality": ("R3_distractor_plausibility", "unique_options"),
    "self_contained": ("self_contained",),
    "rendering_safe": ("rendering_safe",),
}
# The production prompt wants a subject name and topic; EvalQuestion carries a code and a subtopic only.
_SUBJECT_NAMES = {"MATH": "Mathematics", "SCI": "Science", "ENG": "English Language"}


def _subtopic_info(question: EvalQuestion) -> dict[str, Any]:
    return {
        "subject_code": question.subject_code,
        "subject_name": _SUBJECT_NAMES.get(question.subject_code, question.subject_code),
        "grade_level": question.grade_level,
        "topic_name": question.subtopic_name,
        "subtopic_name": question.subtopic_name,
        "learning_objective": question.learning_objective,
    }


async def run_prod_judge(question: EvalQuestion, run_id: str | None = None) -> dict[str, Any]:
    """One production-judge call for one question; returns its ``validations`` dict (``{}`` if unusable)."""
    prompt = build_validation_prompt(_subtopic_info(question), [question.to_bank_dict()])
    with llm_component(JUDGE_COMPONENT, run_id=run_id):
        reply = await complete(
            task=PROD_JUDGE_TASK,
            messages=[
                {"role": "system", "content": QUALITY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=QUALITY_TEMPERATURE,
            max_tokens=QUALITY_MAX_TOKENS,
        )
    try:
        results = parse_validation_response(reply)
    except ValidationResponseError as exc:
        logger.warning("prod_judge_reply_unparseable", question_id=question.id, error=str(exc))
        return {}
    validations = results[0].get("validations") if results else None
    return validations if isinstance(validations, dict) else {}


def map_prod_verdict(validations: dict[str, Any]) -> dict[str, bool | None]:
    """Production verdicts -> calibration criterion ids. Missing or non-boolean ``pass`` is ``None``."""
    mapped: dict[str, bool | None] = {}
    for prod_name, criteria in CRITERION_MAP.items():
        entry = validations.get(prod_name)
        verdict = entry.get("pass") if isinstance(entry, dict) else None
        for criterion in criteria:
            mapped[criterion] = verdict if isinstance(verdict, bool) else None
    return mapped


def prod_verdicts_for_case(
    case_id: str,
    defect: str | None,
    subset: Literal["computed", "authored"],
    scheduled: Sequence[tuple[str, bool]],
    mapped: dict[str, bool | None],
) -> list[CalibrationVerdict]:
    """Verdicts for the scheduled criteria the production judge has an opinion on."""
    return [
        CalibrationVerdict(case_id, criterion, defect, expected, mapped[criterion], subset)
        for criterion, expected in scheduled
        if criterion in mapped
    ]
