"""Unit tests for seed_curriculum_graph validation and dry-run safety.

These cover the pre-flight guards added for the v2 curriculum remap: validate_json
must reject data that would otherwise fail mid-seed against a DB constraint, and
--dry-run must complete without a database connection.
"""

from typing import Any

import pytest

from scripts.seed_curriculum_graph import CurriculumSeeder, Stats, validate_json


def _minimal_data(**subtopic_overrides: Any) -> dict[str, Any]:
    """Build a valid single-subtopic curriculum document."""
    subtopic: dict[str, Any] = {
        "name": "Using negative numbers",
        "canonical_code": "MATH-INTEGERS-G6-USINGNEGATI",
        "learning_objective": "Order and use negative numbers in practical contexts.",
        "bloom_taxonomy_level": "Apply",
        "difficulty_level": 1,
        "sequence_order": 1,
    }
    subtopic.update(subtopic_overrides)
    return {
        "curricula": [{"code": "cambridge_lower", "name": "Cambridge Lower Secondary"}],
        "subjects": [{"code": "MATH", "name": "Mathematics", "subject_family_code": "MATH"}],
        "grades": [{"level": 6, "name": "Grade 6"}],
        "curriculum_subjects": [
            {"curriculum_code": "cambridge_lower", "subject_code": "MATH", "is_core": True, "sort_order": 1}
        ],
        "curriculum_tree": [
            {
                "curriculum_code": "cambridge_lower",
                "subject_code": "MATH",
                "grade_level": 6,
                "topics": [
                    {
                        "name": "Integers",
                        "canonical_code": "MATH-INTEGERS",
                        "sequence_order": 1,
                        "subtopics": [subtopic],
                    }
                ],
            }
        ],
    }


class TestValidateJson:
    """Tests for validate_json pre-flight checks."""

    def test_validate_when_document_is_well_formed_then_returns_no_errors(self) -> None:
        assert validate_json(_minimal_data()) == []

    @pytest.mark.parametrize("tier", ["CORE", "EXTENDED", "BOTH"])
    def test_validate_when_tier_is_valid_then_returns_no_errors(self, tier: str) -> None:
        assert validate_json(_minimal_data(tier=tier)) == []

    def test_validate_when_tier_omitted_then_returns_no_errors(self) -> None:
        # Lower Secondary data carries no tier key; it defaults to BOTH at seed time.
        data = _minimal_data()
        assert "tier" not in data["curriculum_tree"][0]["topics"][0]["subtopics"][0]
        assert validate_json(data) == []

    def test_validate_when_tier_is_unknown_then_reports_error(self) -> None:
        errors = validate_json(_minimal_data(tier="PREMIUM"))
        assert any("invalid tier 'PREMIUM'" in e for e in errors)

    def test_validate_when_canonical_code_exceeds_column_width_then_reports_error(self) -> None:
        # subtopics.canonical_code is VARCHAR(50).
        errors = validate_json(_minimal_data(canonical_code="M" * 51))
        assert any("exceeds 50 chars" in e for e in errors)

    def test_validate_when_canonical_code_is_exactly_fifty_chars_then_no_error(self) -> None:
        assert validate_json(_minimal_data(canonical_code="M" * 50)) == []

    def test_validate_when_learning_objective_is_blank_then_reports_error(self) -> None:
        # learning_objective is NOT NULL and is the LO de-duplication basis.
        errors = validate_json(_minimal_data(learning_objective="   "))
        assert any("empty learning_objective" in e for e in errors)

    def test_validate_when_canonical_code_duplicated_across_grades_then_reports_error(self) -> None:
        # The seeder upserts on canonical_code, so a duplicate would silently bind
        # two curriculum placements to a single subtopic row.
        data = _minimal_data()
        grade_seven = {
            "curriculum_code": "cambridge_lower",
            "subject_code": "MATH",
            "grade_level": 7,
            "topics": [
                {
                    "name": "Integers",
                    "canonical_code": "MATH-INTEGERS",
                    "sequence_order": 1,
                    "subtopics": [dict(data["curriculum_tree"][0]["topics"][0]["subtopics"][0])],
                }
            ],
        }
        data["curriculum_tree"].append(grade_seven)

        errors = validate_json(data)
        assert any("duplicate subtopic canonical_code" in e for e in errors)

    def test_validate_when_subject_code_unknown_then_reports_error(self) -> None:
        data = _minimal_data()
        data["curriculum_tree"][0]["subject_code"] = "ENG"
        errors = validate_json(data)
        assert any("unknown subject_code 'ENG'" in e for e in errors)


class TestDryRunSafety:
    """Tests that --dry-run never touches the database."""

    async def test_seed_interest_categories_when_dry_run_then_does_not_touch_db(self) -> None:
        """Regression: this helper queried self.db unguarded, so --dry-run crashed
        with db=None before any validation output was produced."""
        seeder = CurriculumSeeder(db=None, stats=Stats(), dry_run=True)  # type: ignore[arg-type]

        await seeder._seed_interest_categories()

    async def test_full_seed_when_dry_run_then_completes_without_db(self) -> None:
        seeder = CurriculumSeeder(db=None, stats=Stats(), dry_run=True)  # type: ignore[arg-type]

        await seeder.seed(_minimal_data())

        assert seeder.stats.subtopics == 1
        assert seeder.stats.curricula == 1
