"""Celery tasks for the Kaihle platform."""
from .report_generation import generate_assessment_reports
from .study_plan import generate_study_plan

__all__ = ["generate_assessment_reports", "generate_study_plan"]
