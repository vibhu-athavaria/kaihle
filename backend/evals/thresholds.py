"""Re-export of the pre-registered calibration thresholds; the values live in ``app.ai.eval.thresholds``."""

from app.ai.eval.thresholds import FALSE_ALARM_UPPER_MAX, MIN_N, RECALL_LOWER_MIN

__all__ = ["FALSE_ALARM_UPPER_MAX", "MIN_N", "RECALL_LOWER_MIN"]
