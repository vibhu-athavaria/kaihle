"""Pydantic schema for LLM-generated lesson plan content validation."""

from pydantic import BaseModel


class Misconception(BaseModel):
    student_error: str
    trigger_phrase: str
    recovery_script: str


class KeyConcept(BaseModel):
    name: str
    duration_minutes: int
    teacher_does: str
    student_does: str
    check_question: str
    misconception: Misconception
    transition_cue: str | None = None


class GroupActivity(BaseModel):
    description: str
    stuck_prompt: str


class GroupActivities(BaseModel):
    foundation: GroupActivity
    core: GroupActivity
    extension: GroupActivity


class TimedActivity(BaseModel):
    duration_minutes: int
    activity: str


class TimeBreakdown(BaseModel):
    starter_minutes: int
    intro_minutes: int
    activity_minutes: int
    exit_ticket_minutes: int
    plenary_minutes: int


class ExitTicketQuestion(BaseModel):
    label: str
    question_text: str
    good_answer: str
    pivot_if_wrong: str


class ExitTicket(BaseModel):
    questions: list[ExitTicketQuestion]


class LessonPlanContent(BaseModel):
    lesson_hook: str
    time_breakdown: TimeBreakdown
    learning_objectives: list[str]
    key_concepts: list[KeyConcept]
    group_activities: GroupActivities
    resources_needed: list[str]
    exit_ticket: ExitTicket
    starter: TimedActivity
    plenary: TimedActivity
    prior_knowledge: str
    homework: str | None = None
