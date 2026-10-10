import os

# SD-4: must run before any deepeval import. Forced, not setdefault: a shell exporting NO loses.
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

import pytest  # noqa: E402

from evals.judge import judge_config_problem  # noqa: E402

LIVE_MARKER = "live_eval"
GRADED_TASK = "grade_open_answer"


def live_eval_skip_reason(task: str = GRADED_TASK) -> str | None:
    """Skip reason for live tests, derived from the same checks the judge guards enforce."""
    problem = judge_config_problem(task)
    return None if problem is None else f"live eval skipped: {problem}"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"{LIVE_MARKER}: live LLM evaluation; skipped unless judge and graded model are configured"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live tests with an explicit reason when the judge or graded model is unconfigured."""
    reason = live_eval_skip_reason()
    if reason is None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if LIVE_MARKER in item.keywords:
            item.add_marker(skip)
