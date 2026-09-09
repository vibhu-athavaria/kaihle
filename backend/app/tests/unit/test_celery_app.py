"""Unit tests for the Celery LLM-component attribution signal handlers."""

from types import SimpleNamespace

from structlog.contextvars import clear_contextvars, get_contextvars

from app.tasks.celery_app import _bind_llm_component, _clear_llm_component


class TestBindLlmComponent:
    def teardown_method(self) -> None:
        clear_contextvars()

    def test_bind_llm_component_when_full_dotted_name_then_trimmed_to_task_name(self) -> None:
        sender = SimpleNamespace(name="app.tasks.mini_course_tasks.generate_topic_mini_course")

        _bind_llm_component(sender, task_id="task-1")

        assert get_contextvars()["llm_component"] == "celery:generate_topic_mini_course"

    def test_bind_llm_component_when_name_missing_then_unknown(self) -> None:
        sender = SimpleNamespace()

        _bind_llm_component(sender, task_id="task-2")

        assert get_contextvars()["llm_component"] == "celery:unknown"

    def test_bind_llm_component_when_called_then_request_id_bound_too(self) -> None:
        sender = SimpleNamespace(name="app.tasks.lesson_plan_tasks.generate_lesson_plan")

        _bind_llm_component(sender, task_id="task-3")

        assert get_contextvars()["request_id"] == "task-3"

    def test_clear_llm_component_when_called_then_contextvars_empty(self) -> None:
        sender = SimpleNamespace(name="app.tasks.mini_course_tasks.generate_topic_mini_course")
        _bind_llm_component(sender, task_id="task-4")

        _clear_llm_component(sender)

        assert get_contextvars() == {}
