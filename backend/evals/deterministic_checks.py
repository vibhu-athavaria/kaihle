"""Deterministic checks over ``EvalQuestion`` (SD-12: anything checkable in code is checked in code).

The pure checks moved to ``app.ai.eval.question_checks`` (DeepEval-free, importable from production,
MLH-T18 slice 5a) and are re-exported here so existing imports keep working. ``check_bank_schema``
stays in this module: it wraps the production bank validator in ``scripts.generate_gap_questions``,
and tests patch ``evals.deterministic_checks.validate_question``.
"""

from app.ai.eval.question_checks import (
    MAX_SHARED_OPENER,
    MAX_TRUE_FALSE_SHARE,
    MIN_ANSWER_TEXT_CHARS,
    OPENER_WORD_COUNT,
    CheckResult,
    KeyDistribution,
    check_answer_not_in_stem,
    check_no_compliance_language,
    check_no_duplicate_questions_in_set,
    check_rendering_safe,
    check_self_contained,
    check_stem_opener_variety,
    check_true_false_share,
    check_unique_options,
    find_banned_phrases,
    summarise_key_distribution,
)
from evals.question_model import EvalQuestion
from scripts.generate_gap_questions import validate_question

__all__ = [
    "MAX_SHARED_OPENER",
    "MAX_TRUE_FALSE_SHARE",
    "MIN_ANSWER_TEXT_CHARS",
    "OPENER_WORD_COUNT",
    "CheckResult",
    "KeyDistribution",
    "check_answer_not_in_stem",
    "check_bank_schema",
    "check_no_compliance_language",
    "check_no_duplicate_questions_in_set",
    "check_rendering_safe",
    "check_self_contained",
    "check_stem_opener_variety",
    "check_true_false_share",
    "check_unique_options",
    "find_banned_phrases",
    "summarise_key_distribution",
]


def check_bank_schema(question: EvalQuestion) -> CheckResult:
    """Wrap the production bank validator; its error strings become ``detail``."""
    errors = validate_question(question.to_bank_dict(), question.subject_code)
    return CheckResult("bank_schema", not errors, "; ".join(errors))
