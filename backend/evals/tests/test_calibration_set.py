"""Offline tests for the maths templates, defect mutations and the byte-reproducible calibration set."""

import json
import re
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from evals.calibration_set.build import SHIPPED_PATH, load_calibration_cases, write_calibration_set
from evals.calibration_set.math_templates import SEED, build_math_questions, option_value
from evals.calibration_set.mutations import DEFECTS, MUTATIONS, MutationRecord
from evals.deterministic_checks import check_rendering_safe, check_unique_options, find_banned_phrases
from evals.question_model import OPTION_KEYS, EvalQuestion
from evals.question_rubrics import explanation_spec, understanding_spec
from evals.thresholds import MIN_N

_NUM = r"(\d+)"


def _independent_key(stem: str) -> Fraction:
    """Recompute the answer from the stem text alone, without the generator's code."""
    if m := re.fullmatch(rf"What is the value of {_NUM} \+ {_NUM} × {_NUM}\?", stem):
        a, b, c = map(int, m.groups())
        return Fraction(a + b * c)
    if m := re.fullmatch(rf"What is {_NUM}% of {_NUM}\?", stem):
        p, n = map(int, m.groups())
        return Fraction(p * n, 100)
    if m := re.fullmatch(rf"Solve for x: {_NUM}x \+ {_NUM} = {_NUM}\. What is x\?", stem):
        a, b, c = map(int, m.groups())
        return Fraction(c - b, a)
    if m := re.fullmatch(
        rf"A rectangle is {_NUM} cm long and {_NUM} cm wide\. What is its (area|perimeter) .*\?", stem
    ):
        length, width = int(m.group(1)), int(m.group(2))
        return Fraction(length * width if m.group(3) == "area" else 2 * (length + width))
    if m := re.fullmatch(rf"What is {_NUM}/{_NUM} \+ {_NUM}/{_NUM}\?", stem):
        a, b, c, d = map(int, m.groups())
        return Fraction(a, b) + Fraction(c, d)
    if m := re.fullmatch(r"What is the mean of ([\d, ]+)\?", stem):
        values = [int(v) for v in m.group(1).split(",")]
        return Fraction(sum(values), len(values))
    raise AssertionError(f"unrecognised stem: {stem}")


@pytest.fixture(scope="module")
def questions() -> list[EvalQuestion]:
    return build_math_questions()


def _apply(defect: str, question: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    return MUTATIONS[defect](question)


def test_wrong_key_when_applied_then_key_points_to_a_different_valid_option_and_rest_unchanged(
    questions: list[EvalQuestion],
) -> None:
    q = questions[0]
    mutated, _ = _apply("wrong_key", q)
    assert mutated.correct_answer in OPTION_KEYS and mutated.correct_answer != q.correct_answer
    assert replace(mutated, correct_answer=q.correct_answer) == q


def test_two_correct_when_applied_then_a_distractor_is_numerically_equal_to_the_key_value(
    questions: list[EvalQuestion],
) -> None:
    q = questions[0]
    mutated, _ = _apply("two_correct", q)
    key_value = option_value(q.options[q.correct_answer])
    equal = [k for k in OPTION_KEYS if option_value(mutated.options[k]) == key_value]
    assert len(equal) == 2 and q.correct_answer in equal
    assert mutated.options[q.correct_answer] == q.options[q.correct_answer]


def test_duplicate_option_when_applied_then_two_options_are_identical(questions: list[EvalQuestion]) -> None:
    q = questions[0]
    mutated, _ = _apply("duplicate_option", q)
    assert check_unique_options(q).passed and not check_unique_options(mutated).passed
    assert mutated.options[q.correct_answer] == q.options[q.correct_answer]


def test_absurd_distractor_when_applied_then_value_is_outside_the_plausible_range(
    questions: list[EvalQuestion],
) -> None:
    q = questions[0]
    mutated, _ = _apply("absurd_distractor", q)
    changed = [k for k in OPTION_KEYS if mutated.options[k] != q.options[k]]
    assert len(changed) == 1 and changed[0] != q.correct_answer
    plausible = max(abs(option_value(v)) for v in q.options.values())
    value = option_value(mutated.options[changed[0]])
    assert value < 0 and abs(value) > 10 * plausible


def test_diagram_reference_when_applied_then_stem_starts_with_the_reference_phrase(
    questions: list[EvalQuestion],
) -> None:
    mutated, _ = _apply("diagram_reference", questions[0])
    assert mutated.question_text.startswith("Refer to the diagram below. ")
    assert mutated.question_text.endswith(questions[0].question_text)


def test_latex_markup_when_applied_then_check_rendering_safe_fails(questions: list[EvalQuestion]) -> None:
    assert check_rendering_safe(questions[0]).passed
    mutated, _ = _apply("latex_markup", questions[0])
    assert not check_rendering_safe(mutated).passed


def test_off_objective_when_applied_then_objective_differs_from_the_original(questions: list[EvalQuestion]) -> None:
    mutated, _ = _apply("off_objective", questions[0])
    assert mutated.learning_objective != questions[0].learning_objective


def test_grade_mismatch_when_applied_then_grade_differs_by_at_least_three(questions: list[EvalQuestion]) -> None:
    mutated, _ = _apply("grade_mismatch", questions[0])
    assert abs(mutated.grade_level - questions[0].grade_level) >= 3


def test_explanation_contradicts_key_when_applied_then_explanation_names_a_different_option(
    questions: list[EvalQuestion],
) -> None:
    q = questions[0]
    mutated, _ = _apply("explanation_contradicts_key", q)
    named = re.findall(r"option ([A-D])\b", mutated.explanation)
    assert named and q.correct_answer not in named


@pytest.mark.parametrize("defect", DEFECTS)
def test_every_mutation_when_applied_then_input_question_is_not_modified(
    questions: list[EvalQuestion], defect: str
) -> None:
    q = questions[1]
    before = (dict(q.options), q.question_text, q.explanation, q.learning_objective, q.grade_level, q.correct_answer)
    _apply(defect, q)
    assert before == (
        dict(q.options),
        q.question_text,
        q.explanation,
        q.learning_objective,
        q.grade_level,
        q.correct_answer,
    )


@pytest.mark.parametrize("defect", DEFECTS)
def test_every_mutation_when_applied_then_record_lists_at_least_one_must_fail_criterion(
    questions: list[EvalQuestion], defect: str
) -> None:
    _, record = _apply(defect, questions[1])
    assert record.defect == defect and record.must_fail
    assert not set(record.must_fail) & set(record.must_pass)


def test_mutation_records_when_mapped_then_must_fail_uses_r6_r7_variant_ids_of_existing_specs(
    questions: list[EvalQuestion],
) -> None:
    q = questions[0]
    _, rec = _apply("explanation_contradicts_key", q)
    assert set(rec.must_fail) == {explanation_spec("bank").id, explanation_spec("quiz").id}
    _, other = _apply("off_objective", q)
    assert understanding_spec(q.difficulty_band).id in other.must_pass
    assert explanation_spec("bank").id in other.must_pass and explanation_spec("quiz").id in other.must_pass


def test_math_templates_when_built_then_every_key_matches_an_independent_recomputation(
    questions: list[EvalQuestion],
) -> None:
    for q in questions:
        assert option_value(q.options[q.correct_answer]) == _independent_key(q.question_text), q.question_text


def test_math_templates_when_built_then_exactly_one_option_equals_the_key_value(questions: list[EvalQuestion]) -> None:
    for q in questions:
        values = [option_value(q.options[k]) for k in OPTION_KEYS]
        assert values.count(option_value(q.options[q.correct_answer])) == 1, q.question_text


def test_math_templates_when_built_then_stems_are_unique(questions: list[EvalQuestion]) -> None:
    assert len(questions) >= 40
    assert len({q.question_text for q in questions}) == len(questions)


def test_math_templates_when_built_twice_then_output_is_identical(questions: list[EvalQuestion]) -> None:
    assert build_math_questions() == questions
    assert isinstance(SEED, int)


def test_build_calibration_set_when_run_twice_then_output_files_are_byte_identical(tmp_path: Path) -> None:
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_calibration_set(first)
    write_calibration_set(second)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == SHIPPED_PATH.read_bytes()


def test_shipped_calibration_set_when_loaded_then_at_least_40_clean_computed_math_questions() -> None:
    clean = [c for c in load_calibration_cases() if c.defect is None]
    assert len(clean) >= 40 and all(c.question.subject_code == "MATH" for c in clean)


def test_shipped_calibration_set_when_loaded_then_every_defect_type_has_at_least_20_math_cases() -> None:
    cases = load_calibration_cases()
    for defect in DEFECTS:
        assert sum(c.defect == defect for c in cases) >= MIN_N, defect


def test_shipped_calibration_set_when_loaded_then_math_cases_flagged_computed_with_valid_schedule() -> None:
    for c in load_calibration_cases():
        assert c.label_source == "computed" and c.subset == "computed"
        assert set(c.must_pass_sample) <= set(c.must_pass)
        assert len(c.must_pass_sample) == (0 if c.defect is None else 2)
        assert c.defect is None or c.must_fail


def test_shipped_calibration_set_when_scanned_then_no_emails_uuids_or_banned_phrases() -> None:
    text = Path(SHIPPED_PATH).read_text()
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    assert not find_banned_phrases(text)
    assert all(json.loads(line) for line in text.splitlines())
