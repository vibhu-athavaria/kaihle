"""Pre-registered calibration thresholds (T10 D4).

These were fixed BEFORE any calibration run and MUST NEVER be tuned after seeing results: a
threshold chosen after the data is not a threshold. Change them only in a PR whose description
says so explicitly; ``test_thresholds_when_imported_then_equal_the_preregistered_constants``
guards the values.
"""

# Minimum evaluable (non-indeterminate) cases per cell (recall and false-alarm) for a verdict.
MIN_N = 20
# Wilson LOWER bound on recall (seeded defects detected) must reach this.
RECALL_LOWER_MIN = 0.70
# Wilson UPPER bound on false-alarm rate (clean cases failed) must not exceed this.
FALSE_ALARM_UPPER_MAX = 0.15
