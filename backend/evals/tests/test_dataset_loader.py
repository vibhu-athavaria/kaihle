"""Offline tests for the grade_open_answer golden-dataset loader and the shipped dataset."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evals.loader import GRADES, REQUIRED_EDGE_TAGS, GradeCase, load_grade_cases

SHIPPED = Path(__file__).resolve().parent.parent / "datasets" / "grade_open_answer.jsonl"
BANNED_PHRASES = ("cambridge-compliant", "exam-ready", "ib-aligned", "examination-ready")


def _row(case_id: str = "T-001", **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": case_id,
        "subject": "Mathematics",
        "grade_level": 7,
        "subtopic_name": "Fractions",
        "learning_objective": "Add fractions with unlike denominators",
        "question_text": "Why do we need a common denominator?",
        "student_answer": "So the parts are the same size.",
        "expected_grade": "correct",
        "tags": [],
        "rationale": "States the key idea.",
        "label_source": "model-authored-unvalidated",
    }
    row.update(overrides)
    return row


def _write(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_load_grade_cases_when_valid_file_then_returns_typed_cases(tmp_path: Path) -> None:
    path = _write(tmp_path, [_row("T-002"), _row("T-001", learning_objective=None, tags=["terse_correct"])])

    cases = load_grade_cases(path)

    assert [c.id for c in cases] == ["T-002", "T-001"]
    assert all(isinstance(c, GradeCase) for c in cases)
    assert cases[1].learning_objective is None
    assert cases[1].tags == ["terse_correct"]


def test_load_grade_cases_when_duplicate_ids_then_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, [_row("T-001"), _row("T-001")])

    with pytest.raises(ValueError, match="T-001"):
        load_grade_cases(path)


def test_load_grade_cases_when_unknown_expected_grade_then_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, [_row("T-009", expected_grade="excellent")])

    with pytest.raises(ValueError, match="T-009") as exc:
        load_grade_cases(path)
    assert "expected_grade" in str(exc.value)


def test_load_grade_cases_when_unknown_tag_then_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, [_row("T-010", tags=["made_up_tag"])])

    with pytest.raises(ValueError, match="T-010") as exc:
        load_grade_cases(path)
    assert "tags" in str(exc.value)


def test_load_grade_cases_when_label_source_missing_then_raises(tmp_path: Path) -> None:
    row = _row("T-011")
    del row["label_source"]
    path = _write(tmp_path, [row])

    with pytest.raises(ValueError, match="T-011") as exc:
        load_grade_cases(path)
    assert "label_source" in str(exc.value)


def test_grade_case_when_label_source_not_the_literal_then_validation_error() -> None:
    with pytest.raises(ValidationError):
        GradeCase(**_row(label_source="human-validated"))


@pytest.fixture(scope="module")
def shipped() -> list[GradeCase]:
    return load_grade_cases(SHIPPED)


def test_shipped_grade_dataset_when_loaded_then_meets_size_and_class_balance(shipped: list[GradeCase]) -> None:
    counts: Counter[str] = Counter(c.expected_grade for c in shipped)

    assert len(shipped) >= 60
    assert all(counts[g] >= 15 for g in GRADES)


def test_shipped_grade_dataset_when_loaded_then_covers_every_required_edge_tag_at_least_three_times(
    shipped: list[GradeCase],
) -> None:
    counts: Counter[str] = Counter(t for c in shipped for t in c.tags)

    assert all(counts[tag] >= 3 for tag in REQUIRED_EDGE_TAGS)


def test_shipped_grade_dataset_when_loaded_then_spans_required_subjects(shipped: list[GradeCase]) -> None:
    subjects = {c.subject for c in shipped}
    grade_levels = {c.grade_level for c in shipped}

    assert {"Mathematics", "Science", "English"} <= subjects
    assert grade_levels == {6, 7, 8, 9, 10}


def test_shipped_grade_dataset_when_scanned_then_contains_no_emails_or_uuids() -> None:
    raw = SHIPPED.read_text(encoding="utf-8")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    uuid = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

    assert email.search(raw) is None
    assert uuid.search(raw) is None


def test_shipped_grade_dataset_when_scanned_then_contains_no_banned_compliance_phrases() -> None:
    raw = SHIPPED.read_text(encoding="utf-8").lower()

    assert [p for p in BANNED_PHRASES if p in raw] == []
