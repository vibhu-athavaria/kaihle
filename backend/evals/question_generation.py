"""Question-bank generation adapter (T10 Step 9, bank path).

Runs the PRODUCTION prompt builder (``build_prompt``), router call (task ``question_generation`` with
the ``GENERATION_*`` constants), response parser (``parse_generation_response``), text cleaner and
schema validator (``validate_question``), then converts the multiple-choice questions to
``EvalQuestion``. True/false questions are set aside and counted: the MCQ rubrics do not apply to them.

A reply the production parser rejects is a structural outcome, not an exception. Router exceptions
propagate so a run never silently reports a smaller sample (production retries and swallows; the eval
wants to see failures). Specs are synthetic: no real subtopic ids, no student data.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from app.ai.providers.router import complete
from app.ai.usage_context import llm_component
from evals.judge import JUDGE_COMPONENT
from evals.question_model import DifficultyBand, EvalQuestion
from scripts.generate_gap_questions import (
    GENERATION_MAX_TOKENS,
    GENERATION_SYSTEM_PROMPT,
    GENERATION_TEMPERATURE,
    build_prompt,
    clean_question,
    parse_generation_response,
    validate_question,
)

logger = structlog.get_logger()

BANK_TASK = "question_generation"
SPECS_PATH = Path(__file__).resolve().parent / "datasets" / "question_generation_specs.jsonl"
MULTIPLE_CHOICE = "multiple_choice"
TRUE_FALSE = "true_false"
# Bank difficulty 1-5 -> the three bands the rubrics are parameterised by (T10 D7a).
_FOUNDATIONAL_MAX_LEVEL = 2
_DEVELOPING_LEVEL = 3

OutcomeStatus = Literal["ok", "unparseable", "no_questions"]


class GenerationSpec(BaseModel):
    """One synthetic subtopic spec. ``mastery`` is used only by the (not yet built) quiz path."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    subject_code: str
    subject_name: str
    grade_level: int
    topic_name: str
    subtopic_name: str
    learning_objective: str
    curriculum_name: str
    curriculum_code: str
    mastery: Literal["low", "mid", "high"]


@dataclass(frozen=True)
class BankOutcome:
    spec_id: str
    status: OutcomeStatus
    questions: list[EvalQuestion] = field(default_factory=list)
    true_false_count: int = 0
    # One "<preview>: <errors>" string per MCQ the production validator (or EvalQuestion) rejected.
    schema_failures: list[str] = field(default_factory=list)


def load_generation_specs(path: Path = SPECS_PATH) -> list[GenerationSpec]:
    """Load and validate the JSONL specs; raise ValueError naming the spec id on any defect."""
    specs: list[GenerationSpec] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            spec_id = str(raw.get("spec_id", f"<line {line_no}>")) if isinstance(raw, dict) else f"<line {line_no}>"
            try:
                specs.append(GenerationSpec.model_validate(raw))
            except ValidationError as exc:
                raise ValueError(f"spec {spec_id}: {exc}") from exc
    if len({s.spec_id for s in specs}) != len(specs):
        raise ValueError("duplicate spec_id in generation specs")
    return specs


def prompt_subtopic(spec: GenerationSpec) -> dict[str, Any]:
    """The subtopic dict ``build_prompt`` expects, from a synthetic spec."""
    return {
        "subject_code": spec.subject_code,
        "subject_name": spec.subject_name,
        "grade_level": spec.grade_level,
        "topic_name": spec.topic_name,
        "subtopic_name": spec.subtopic_name,
        "learning_objective": spec.learning_objective,
        "curriculum_name": spec.curriculum_name,
        "curriculum_code": spec.curriculum_code,
    }


def band_for_level(level: int) -> DifficultyBand:
    if level <= _FOUNDATIONAL_MAX_LEVEL:
        return "foundational"
    return "developing" if level == _DEVELOPING_LEVEL else "advanced"


def _to_eval_question(raw: dict[str, Any], spec: GenerationSpec, index: int) -> EvalQuestion:
    return EvalQuestion.from_bank_dict(
        raw,
        id=f"{spec.spec_id}-q{index:02d}",
        subject_code=spec.subject_code,
        grade_level=spec.grade_level,
        subtopic_name=spec.subtopic_name,
        difficulty_band=band_for_level(int(float(raw["difficulty_level"]))),
    )


async def generate_bank_outcome(spec: GenerationSpec, run_id: str | None = None) -> BankOutcome:
    """One production-shaped generation call for one spec. Side effect: a router call (LLM spend)."""
    prompt = build_prompt(prompt_subtopic(spec))
    with llm_component(JUDGE_COMPONENT, run_id=run_id):
        reply = await complete(
            task=BANK_TASK,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=GENERATION_TEMPERATURE,
            max_tokens=GENERATION_MAX_TOKENS,
        )
    try:
        batch = parse_generation_response(reply)
    except json.JSONDecodeError as exc:
        logger.warning("bank_reply_unparseable", spec_id=spec.spec_id, error=str(exc))
        return BankOutcome(spec.spec_id, "unparseable")
    # Production calls ``batch.get`` unguarded, so a bare list would crash it; here it is just structural.
    if not isinstance(batch, dict):
        logger.warning("bank_reply_not_an_object", spec_id=spec.spec_id)
        return BankOutcome(spec.spec_id, "unparseable")
    raw_questions = batch.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        return BankOutcome(spec.spec_id, "no_questions")

    questions: list[EvalQuestion] = []
    failures: list[str] = []
    true_false = 0
    for index, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            failures.append(f"question {index}: not an object")
            continue
        cleaned = clean_question(item)
        if cleaned.get("question_type") == TRUE_FALSE:
            true_false += 1
            continue
        label = f"question {index}"
        errors = validate_question(cleaned, spec.subject_code)
        if errors:
            failures.append(f"{label}: {'; '.join(errors)}")
            continue
        try:
            questions.append(_to_eval_question(cleaned, spec, index))
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(f"{label}: cannot build EvalQuestion ({type(exc).__name__}: {exc})")
    return BankOutcome(spec.spec_id, "ok", questions, true_false, failures)
