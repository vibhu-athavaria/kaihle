"""Usage event -> `EvalQuestion` for production task ``question_generation`` (MLH-T18 slice 5b-i).

A stored event is one bank-generator call: ``response_text`` is the batch JSON
(``{"questions": [...]}``, up to 15 questions, MCQ and true/false) and ``prompt_text`` holds the
curriculum block that carries the grade, subject and subtopic the rubrics need.

PARSER DECISION. The production parser lives in ``scripts/generate_gap_questions.py`` and ``app/``
cannot import ``scripts/``. Rather than move it (a refactor of a script with its own tests, in a
slice about wiring) this module has a SMALL TOLERANT parser: strip an optional code fence, decode
JSON, require ``{"questions": [non-empty list]}``. It is read-only and does not validate or clean
questions; ``EvalQuestion`` refuses malformed MCQs. If the script's parser changes shape this one
must follow; both are covered by tests.

ONE QUESTION PER EVENT. ``eval_results`` is unique on (run, event, check), so an event carries one
verdict per check. The adapter therefore picks ONE multiple-choice question per batch, chosen by a
seeded hash (stable for a given run seed, different across seeds). True/false questions are set
aside: the MCQ rubrics do not apply to them. An event with no usable MCQ, or whose prompt lacks the
curriculum block, is "unsupported" and counted by the caller.

NOTHING HERE LOGS OR STORES TEXT.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, replace
from typing import Any

from app.ai.eval.question_model import DifficultyBand, EvalQuestion
from app.services.eval_prod.sampler import SampledEvent
from app.services.eval_prod.scrub import scrub_text

QUESTION_GENERATION_TASK = "question_generation"
_MULTIPLE_CHOICE = "multiple_choice"
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*(.*?)\s*```$", re.DOTALL)
_GRADE_RE = re.compile(r"^-\s*Grade:\s*(\d{1,2})\s*$", re.MULTILINE)
_SUBJECT_RE = re.compile(r"^-\s*Subject:\s*.*\(([A-Za-z0-9_]+)\)\s*$", re.MULTILINE)
_SUBTOPIC_RE = re.compile(r"^-\s*Subtopic:\s*(.+?)\s*$", re.MULTILINE)
# Bank difficulty 1-5 -> rubric bands. Mirrors the offline adapter's mapping (T10 D7a).
_FOUNDATIONAL_MAX_LEVEL = 2
_DEVELOPING_LEVEL = 3


@dataclass(frozen=True)
class QuestionContext:
    grade_level: int
    subject_code: str
    subtopic_name: str


def parse_batch(response_text: str) -> list[dict[str, Any]] | None:
    """The batch's question dicts, or None when the reply is not a usable bank batch."""
    body = response_text.strip()
    fenced = _FENCE_RE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions or not all(isinstance(q, dict) for q in questions):
        return None
    return questions


def parse_context(prompt_text: str | None) -> QuestionContext | None:
    """Grade, subject code and subtopic from the generator prompt's curriculum block, or None."""
    if not prompt_text:
        return None
    grade, subject, subtopic = (
        _GRADE_RE.search(prompt_text),
        _SUBJECT_RE.search(prompt_text),
        _SUBTOPIC_RE.search(prompt_text),
    )
    if grade is None or subject is None or subtopic is None:
        return None
    return QuestionContext(int(grade.group(1)), subject.group(1), subtopic.group(1))


def _band(level: int) -> DifficultyBand:
    if level <= _FOUNDATIONAL_MAX_LEVEL:
        return "foundational"
    return "developing" if level == _DEVELOPING_LEVEL else "advanced"


def _pick_order(event_id: uuid.UUID, seed: str, count: int) -> list[int]:
    """Candidate indexes in seeded, reproducible order."""
    return sorted(range(count), key=lambda i: hashlib.sha256(f"{seed}:{event_id}:{i}".encode()).hexdigest())


def adapt_event(event: SampledEvent, *, seed: str) -> EvalQuestion | None:
    """One seeded-pick MCQ from the event's batch with its curriculum context, or None if unsupported."""
    context = parse_context(event.prompt_text)
    batch = parse_batch(event.response_text)
    if context is None or batch is None:
        return None
    mcqs = [(i, q) for i, q in enumerate(batch) if q.get("question_type") == _MULTIPLE_CHOICE]
    for position in _pick_order(event.id, seed, len(mcqs)):
        index, raw = mcqs[position]
        try:
            return EvalQuestion.from_bank_dict(
                raw,
                id=f"{event.id}-q{index:02d}",
                subject_code=context.subject_code,
                grade_level=context.grade_level,
                subtopic_name=context.subtopic_name,
                difficulty_band=_band(int(float(raw["difficulty_level"]))),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            continue  # a malformed MCQ: try the next candidate
    return None


def scrub_question(question: EvalQuestion, *, person_names: tuple[str, ...], school_name: str | None) -> EvalQuestion:
    """Copy of ``question`` with every free-text field scrubbed. Raises ScrubFailedError (fail closed)."""

    def clean(text: str) -> str:
        return scrub_text(text, person_names=person_names, school_name=school_name)

    return replace(
        question,
        subtopic_name=clean(question.subtopic_name),
        learning_objective=clean(question.learning_objective),
        question_text=clean(question.question_text),
        options={key: clean(text) for key, text in question.options.items()},
        explanation=clean(question.explanation),
    )
