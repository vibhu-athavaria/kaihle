"""Golden-dataset loader for the grade_open_answer evaluation (SD-7: synthetic data only)."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

Grade = Literal["correct", "partial", "incorrect"]
Tag = Literal[
    "off_topic",
    "terse_correct",
    "misspelled_correct",
    "confident_wrong",
    "non_english",
    "prompt_injection",
]

GRADES: tuple[str, ...] = ("correct", "partial", "incorrect")
# Every tag in the fixed set is a required edge case that the shipped dataset must cover.
REQUIRED_EDGE_TAGS: tuple[str, ...] = (
    "off_topic",
    "terse_correct",
    "misspelled_correct",
    "confident_wrong",
    "non_english",
    "prompt_injection",
)


class GradeCase(BaseModel):
    """One labelled grading case. Labels are model-authored and NOT human validated."""

    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    grade_level: int
    subtopic_name: str
    learning_objective: str | None  # None means the prompt omits the objective section
    question_text: str
    student_answer: str
    expected_grade: Grade
    tags: list[Tag]
    rationale: str
    label_source: Literal["model-authored-unvalidated"]


def _describe(case_id: str, err: ValidationError) -> str:
    fields = sorted({".".join(str(p) for p in e["loc"]) for e in err.errors()})
    return f"case {case_id}: invalid field(s) {', '.join(fields)}: {err.errors()[0]['msg']}"


def load_grade_cases(path: Path) -> list[GradeCase]:
    """Load and validate a JSONL file; raise ValueError naming the case id and field on any defect."""
    cases: list[GradeCase] = []
    seen: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        case_id = str(raw.get("id", f"<line {line_no}>")) if isinstance(raw, dict) else f"<line {line_no}>"
        try:
            case = GradeCase.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(_describe(case_id, exc)) from exc
        if case.id in seen:
            raise ValueError(f"case {case.id}: duplicate id")
        seen.add(case.id)
        cases.append(case)
    return cases
