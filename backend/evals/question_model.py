"""Canonical MCQ model shared by every question-quality eval.

The definition moved to ``app.ai.eval.question_model`` (DeepEval-free, importable from production,
MLH-T18 slice 5a); every name is re-exported here so existing imports keep working.
"""

from app.ai.eval.question_model import OPTION_KEYS, DifficultyBand, EvalQuestion

__all__ = ["OPTION_KEYS", "DifficultyBand", "EvalQuestion"]
