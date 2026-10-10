"""Pure deterministic checks over ``EvalQuestion`` (SD-12: anything checkable in code is checked in code).

No judge, no DeepEval, no I/O. Heuristic checks say so in their docstrings and are report-only.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from evals.question_model import OPTION_KEYS, EvalQuestion
from scripts.generate_gap_questions import validate_question

MIN_ANSWER_TEXT_CHARS = 4
OPENER_WORD_COUNT = 3
MAX_SHARED_OPENER = 2
MAX_TRUE_FALSE_SHARE = 0.25

# Points at material the student cannot see: assessments are text-only.
_UNSEEN_MATERIAL_RE = re.compile(
    r"\b(?:"
    r"(?:the|this|following|above|below)\s+(?:diagram|figure|graph|chart|image|picture|illustration|drawing|table)"
    r"|(?:diagram|figure|graph|chart|image|picture|table)\s+(?:above|below|shown)"
    r"|refer\s+to\s+the\s+(?:diagram|figure|graph|chart|image|picture|table)"
    r"|shown\s+(?:above|below)"
    r"|as\s+shown"
    r"|see\s+(?:the\s+)?(?:diagram|figure|graph|chart|image|table)"
    r")\b",
    re.IGNORECASE,
)

# Markup that renders literally (no maths/markdown renderer). Unicode x², ½, × is fine.
_UNRENDERABLE_RE = re.compile(
    r"(?:\$[^$\n]{1,80}\$"
    r"|\\(?:frac|sqrt|times|div|leq|geq|neq|approx|pi|alpha|beta|theta|circ|degree)\b"
    r"|\\\(|\\\)|\\\[|\\\]"
    r"|\*\*[^*\n]+\*\*"
    r"|<(?:sub|sup|br|b|i|em|strong|p|div)\b[^>]*>"
    r"|`[^`\n]+`"
    r"|\b[a-zA-Z]\^\d"
    r"|\b[a-zA-Z]\s+(?:squared|cubed)\b)",
    re.IGNORECASE,
)

# Rule 23 / SD-13. Hyphen or space between the words. Extend here, nowhere else.
_COMPLIANCE_RE = re.compile(
    r"\b(?:"
    r"cambridge[\s-]+(?:compliant|aligned|approved)"
    r"|ib[\s-]+(?:aligned|compliant|approved)"
    r"|exam(?:ination)?[\s-]+ready"
    r"|examination[\s-]+board"
    r"|syllabus[\s-]+compliant"
    r"|mark[\s-]+scheme[\s-]+(?:aligned|compliant)"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class KeyDistribution:
    """Answer-key letter counts. Reported, never gated."""

    counts: dict[str, int]
    max_share: float


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _question_texts(question: EvalQuestion) -> list[tuple[str, str]]:
    """Every learner-visible field (stem and options) plus the explanation, labelled."""
    return [
        ("question_text", question.question_text),
        *[(f"option {key}", question.options[key]) for key in OPTION_KEYS],
        ("explanation", question.explanation),
    ]


def find_banned_phrases(text: str) -> list[str]:
    """Rule 23 phrases found in ``text`` (also used on rubric and dataset text, SD-13)."""
    return [match.group(0) for match in _COMPLIANCE_RE.finditer(text)]


def check_unique_options(question: EvalQuestion) -> CheckResult:
    seen: dict[str, list[str]] = {}
    for key in OPTION_KEYS:
        seen.setdefault(_normalise(question.options[key]), []).append(key)
    duplicates = [keys for keys in seen.values() if len(keys) > 1]
    if duplicates:
        return CheckResult("unique_options", False, "duplicate options: " + "; ".join(",".join(k) for k in duplicates))
    return CheckResult("unique_options", True)


def check_self_contained(question: EvalQuestion) -> CheckResult:
    """Fail on references to a diagram/table the learner cannot see (stem and options)."""
    problems = [
        f"{label} refers to {match.group(0)!r}"
        for label, text in _question_texts(question)[:-1]
        if (match := _UNSEEN_MATERIAL_RE.search(text))
    ]
    return CheckResult("self_contained", not problems, "; ".join(problems))


def check_rendering_safe(question: EvalQuestion) -> CheckResult:
    """Fail on LaTeX/markdown/HTML/ASCII-exponent markup that would render literally."""
    problems = [
        f"{label} contains {match.group(0)!r}"
        for label, text in _question_texts(question)[:-1]
        if (match := _UNRENDERABLE_RE.search(text))
    ]
    return CheckResult("rendering_safe", not problems, "; ".join(problems))


def check_no_compliance_language(question: EvalQuestion) -> CheckResult:
    """Rule 23: generated text must say 'curriculum-informed', never claim board compliance."""
    found = [phrase for _, text in _question_texts(question) for phrase in find_banned_phrases(text)]
    return CheckResult("no_compliance_language", not found, "banned phrases: " + ", ".join(found) if found else "")


def check_answer_not_in_stem(question: EvalQuestion) -> CheckResult:
    """HEURISTIC: fail when the correct option's text (>= 4 chars) appears verbatim in the stem.

    Verbatim containment only; paraphrased give-aways are not detected, and a short or numeric
    answer legitimately repeated in the stem is ignored by the length floor. Report-only.
    """
    answer = _normalise(question.options[question.correct_answer])
    if len(answer) >= MIN_ANSWER_TEXT_CHARS and answer in _normalise(question.question_text):
        return CheckResult("answer_not_in_stem", False, f"correct option text {answer!r} appears in the stem")
    return CheckResult("answer_not_in_stem", True)


def check_no_duplicate_questions_in_set(questions: Sequence[EvalQuestion]) -> CheckResult:
    ids_by_stem: dict[str, list[str]] = {}
    for question in questions:
        ids_by_stem.setdefault(_normalise(question.question_text), []).append(question.id)
    duplicates = [ids for ids in ids_by_stem.values() if len(ids) > 1]
    if duplicates:
        return CheckResult(
            "no_duplicate_questions_in_set", False, "duplicate stems: " + "; ".join(",".join(i) for i in duplicates)
        )
    return CheckResult("no_duplicate_questions_in_set", True)


def check_stem_opener_variety(questions: Sequence[EvalQuestion]) -> CheckResult:
    """Fail when 3 or more stems share the same first three words (bank prompt rule)."""
    openers = Counter(
        " ".join(re.findall(r"[a-z0-9']+", question.question_text.lower())[:OPENER_WORD_COUNT])
        for question in questions
    )
    repeated = {opener: n for opener, n in openers.items() if n > MAX_SHARED_OPENER}
    detail = "; ".join(f"{opener!r} x{n}" for opener, n in repeated.items())
    return CheckResult("stem_opener_variety", not repeated, detail)


def check_true_false_share(*, true_false_count: int, total: int) -> CheckResult:
    """Bank only: more than 25% true/false fails. An empty set passes (nothing to share)."""
    share = true_false_count / total if total else 0.0
    return CheckResult(
        "true_false_share", share <= MAX_TRUE_FALSE_SHARE, f"{true_false_count}/{total} true_false ({share:.0%})"
    )


def summarise_key_distribution(questions: Sequence[EvalQuestion]) -> KeyDistribution:
    """Letter counts and the largest share. Reported only: small sets legitimately skew."""
    counts = {key: 0 for key in OPTION_KEYS}
    for question in questions:
        counts[question.correct_answer] += 1
    total = len(questions)
    return KeyDistribution(counts=counts, max_share=max(counts.values()) / total if total else 0.0)


def check_bank_schema(question: EvalQuestion) -> CheckResult:
    """Wrap the production bank validator; its error strings become ``detail``."""
    errors = validate_question(question.to_bank_dict(), question.subject_code)
    return CheckResult("bank_schema", not errors, "; ".join(errors))
