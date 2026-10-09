import os

# SD-4: must run before any deepeval import. Forced, not setdefault: a shell exporting NO loses.
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

import pytest  # noqa: E402

from app.ai.providers.router import TASK_MODEL_MAP  # noqa: E402
from app.core.config import settings  # noqa: E402

LIVE_MARKER = "live_eval"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"{LIVE_MARKER}: live LLM evaluation; skipped unless judge and graded model are configured"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live tests with an explicit reason when the judge or graded model is unconfigured."""
    reason = None
    if not settings.llm_eval_judge_model:
        reason = "live eval skipped: LLM_EVAL_JUDGE_MODEL is not set"
    elif not TASK_MODEL_MAP.get("grade_open_answer"):
        reason = "live eval skipped: LLM_GRADE_OPEN_ANSWER_MODEL is not set"
    if reason is None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if LIVE_MARKER in item.keywords:
            item.add_marker(skip)
