"""Tests for Assessment model after config column removal (T1 migration).

Verifies new typed columns exist with correct defaults, old columns are gone,
and AssessmentTopicConfig model behaves correctly.
"""

import uuid

from sqlalchemy import inspect

from app.models.assessment import Assessment, AssessmentTopicConfig


class TestAssessmentModelNewColumns:
    def test_assessment_model_has_no_config_column_when_inspected_then_attribute_absent(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "config" not in col_names

    def test_assessment_model_has_no_is_system_generated_when_inspected_then_attribute_absent(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "is_system_generated" not in col_names

    def test_assessment_model_has_no_diagnostic_topic_ids_when_inspected_then_attribute_absent(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "diagnostic_topic_ids" not in col_names

    def test_assessment_model_has_no_curriculum_topic_id_when_inspected_then_attribute_absent(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "curriculum_topic_id" not in col_names

    def test_assessment_model_has_time_limit_minutes_when_inspected_then_present(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "time_limit_minutes" in col_names

    def test_assessment_model_has_question_types_when_inspected_then_present(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "question_types" in col_names

    def test_assessment_model_has_minimum_difficulty_when_inspected_then_present(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "minimum_difficulty" in col_names

    def test_assessment_model_has_maximum_difficulty_when_inspected_then_present(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "maximum_difficulty" in col_names

    def test_assessment_model_has_questions_per_topic_when_inspected_then_present(self):
        mapper = inspect(Assessment)
        col_names = [c.key for c in mapper.columns]
        assert "questions_per_topic" in col_names

    def test_assessment_model_defaults_when_inspected_then_correct_column_defaults(self):
        mapper = inspect(Assessment)
        col_defaults = {c.key: c.columns[0].default for c in mapper.column_attrs}

        def arg(key: str) -> object:
            d = col_defaults.get(key)
            return d.arg if d is not None else None

        assert arg("minimum_difficulty") == 1
        assert arg("maximum_difficulty") == 5
        assert arg("questions_per_topic") == 2
        assert arg("time_limit_minutes") == 0
        # question_types default is a callable (lambda), check it returns correct value
        qt_default = col_defaults.get("question_types")
        assert qt_default is not None
        assert qt_default.is_callable
        assert qt_default.arg({}) == ["MCQ", "TRUE_FALSE"]


class TestAssessmentTopicConfigModel:
    def test_assessment_topic_config_model_when_inspected_then_has_required_columns(self):
        mapper = inspect(AssessmentTopicConfig)
        col_names = [c.key for c in mapper.columns]
        assert "assessment_id" in col_names
        assert "curriculum_topic_id" in col_names
        assert "grade_id" in col_names

    def test_assessment_topic_config_when_instantiated_then_fields_assigned(self):
        assessment_id = uuid.uuid4()
        curriculum_topic_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        row = AssessmentTopicConfig(
            assessment_id=assessment_id,
            curriculum_topic_id=curriculum_topic_id,
            grade_id=grade_id,
        )
        assert row.assessment_id == assessment_id
        assert row.curriculum_topic_id == curriculum_topic_id
        assert row.grade_id == grade_id
