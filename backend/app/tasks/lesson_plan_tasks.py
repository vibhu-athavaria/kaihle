"""Lesson plan Celery tasks.

On-demand generation: teacher triggers via POST /classes/{class_id}/lesson-plans/generate.
No weekly beat schedule — replaced by on-demand model.

Real implementation: M4-1-T1.
"""

from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="lesson_plan_tasks.generate_lesson_plan",
)
def generate_lesson_plan_task(
    self: object,
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    gap_summary: dict,
) -> None:
    """Generate a lesson plan via LLM for the given class and subtopics.

    Args:
        lesson_plan_id: UUID of the pre-created LessonPlan row (status=GENERATING).
        class_id: Class UUID string.
        focus_subtopic_ids: Subtopic UUIDs to focus the lesson plan on.
        gap_summary: Snapshot of class mastery at generation time.

    Real implementation (M4-1-T1):
    - Load student learning profiles for the class to get modality distribution.
    - Render lesson_plan.jinja2 prompt with gap_summary + profile aggregate.
    - Call router.py get_provider(task="lesson_plan") to invoke LLM.
    - Parse response and write back to LessonPlan.generated_plan.
    - Set status = GENERATED.
    - Emit CRITICAL log on final retry exhaustion (CONSTITUTION Rule 18).
    """
    # STUB — M4-1-T1
    raise NotImplementedError("Lesson plan generation not yet implemented")
