"""Celery tasks for the Kaihle platform."""
from .report_generation import generate_assessment_reports

__all__ = ["generate_assessment_reports"]
