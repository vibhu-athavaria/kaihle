"""Re-export of the calibration scoring and persistence core, which lives in ``app.ai.eval.calibration``.

This module IS that module at runtime: ``sys.modules`` is pointed at the implementation, so
``evals.calibration`` and ``app.ai.eval.calibration`` are one module object. That keeps patching
(``patch("evals.calibration.logger")``, ``monkeypatch.setattr(calibration, "_path_for", ...)``,
``patch("evals.calibration.os.replace")``) acting on the real code, exactly as before the move.
The explicit imports below exist for static analysis (mypy) of ``from evals.calibration import ...``.
"""

import sys

from app.ai.eval import calibration as _implementation
from app.ai.eval.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationResult,
    CalibrationStatus,
    CalibrationVerdict,
    Subset,
    _path_for,
    calibration_status,
    crosstalk_matrix,
    load_calibration,
    save_calibration,
    score_calibration,
)

__all__ = [
    "DEFAULT_CALIBRATION_DIR",
    "CalibrationResult",
    "CalibrationStatus",
    "CalibrationVerdict",
    "Subset",
    "_path_for",
    "calibration_status",
    "crosstalk_matrix",
    "load_calibration",
    "save_calibration",
    "score_calibration",
]

sys.modules[__name__] = _implementation
