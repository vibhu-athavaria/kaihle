"""Seeded Mathematics MCQ templates. Keys and distractors are computed in code; no model is involved.

Each family builds an exact ``Fraction`` answer plus distractors from explicit error models (wrong
operation, forgotten step, sign error). Options are plain numbers so ``option_value`` can parse any
of them, and so the ``two_correct`` mutation can write an equivalent form (for example ``1/2`` -> ``0.5``).
"""

import random
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction

from evals.question_model import OPTION_KEYS, DifficultyBand, EvalQuestion

SEED = 20261014
PER_FAMILY = 8
SUBJECT_CODE = "MATH"
_BANDS: tuple[DifficultyBand, ...] = ("foundational", "developing", "advanced")
_LEVELS: dict[str, int] = {"foundational": 2, "developing": 3, "advanced": 4}
_MAX_ATTEMPTS = 200

# (stem, answer, distractor candidates in priority order, explanation)
Draft = tuple[str, Fraction, list[Fraction], str]


def fmt(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def option_value(text: str) -> Fraction:
    return Fraction(text.strip())


def equivalent_form(text: str) -> str:
    """A value-equal but textually different decimal form of ``text``. Raises if none terminates."""
    value = option_value(text)
    rest = value.denominator
    for prime in (2, 5):
        while rest % prime == 0:
            rest //= prime
    if rest != 1:
        raise ValueError(f"no terminating decimal form for {text!r}")
    if value.denominator == 1:
        return f"{value.numerator}.0"
    return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def _arithmetic(rng: random.Random) -> Draft:
    a, b, c = rng.randint(2, 9), rng.randint(2, 12), rng.randint(2, 9)
    key = a + b * c
    wrong = [(a + b) * c, a * b + c, a + b + c]
    return (
        f"What is the value of {a} + {b} × {c}?",
        Fraction(key),
        [Fraction(w) for w in wrong],
        f"Multiply before adding: {b} × {c} = {b * c}, then {a} + {b * c} = {key}.",
    )


def _percent(rng: random.Random) -> Draft:
    p, n = rng.choice((10, 20, 25, 30, 40, 50, 60, 75)), rng.randrange(40, 400, 20)
    key = Fraction(p * n, 100)
    return (
        f"What is {p}% of {n}?",
        key,
        [Fraction(p * n), Fraction(p * n, 10), n - key],
        f"{p}% means {p} out of 100, so {p}/100 × {n} = {fmt(key)}.",
    )


def _linear(rng: random.Random) -> Draft:
    a, x, b = rng.randint(2, 9), rng.randint(2, 12), rng.randint(1, 15)
    c = a * x + b
    return (
        f"Solve for x: {a}x + {b} = {c}. What is x?",
        Fraction(x),
        [Fraction(c + b, a), Fraction(c - b), Fraction(x + b)],
        f"Subtract {b} from both sides to get {a}x = {c - b}, then divide by {a}: x = {x}.",
    )


def _rectangle(rng: random.Random) -> Draft:
    length, width = rng.randint(3, 15), rng.randint(2, 12)
    area, perimeter = length * width, 2 * (length + width)
    if rng.random() < 0.5:
        stem = f"A rectangle is {length} cm long and {width} cm wide. What is its area in square centimetres?"
        key, wrong = area, [perimeter, length + width, 2 * area]
        why = f"Area = length × width = {length} × {width} = {area}."
    else:
        stem = f"A rectangle is {length} cm long and {width} cm wide. What is its perimeter in centimetres?"
        key, wrong = perimeter, [area, length + width, 2 * length + width]
        why = f"Perimeter = 2 × ({length} + {width}) = {perimeter}."
    return stem, Fraction(key), [Fraction(w) for w in wrong], why


def _fractions(rng: random.Random) -> Draft:
    b, d = rng.choice((2, 4, 8)), rng.choice((2, 4, 8))
    a, c = rng.randint(1, b - 1), rng.randint(1, d - 1)
    key = Fraction(a, b) + Fraction(c, d)
    return (
        f"What is {a}/{b} + {c}/{d}?",
        key,
        [Fraction(a + c, b + d), Fraction(a * c, b * d), Fraction(a + c, max(b, d))],
        f"Use a common denominator: {a}/{b} + {c}/{d} = {fmt(key)}.",
    )


def _mean(rng: random.Random) -> Draft:
    values = [rng.randint(2, 20) for _ in range(4)]
    values.append((-sum(values)) % 5 + 5 * rng.randint(0, 4) + 5)
    total = sum(values)
    key = Fraction(total, 5)
    return (
        f"What is the mean of {', '.join(map(str, values))}?",
        key,
        [Fraction(total), Fraction(total, 4), key + 1],
        f"Add the values to get {total}, then divide by 5: {fmt(key)}.",
    )


# (draft builder, subtopic, learning objective)
_FAMILIES: tuple[tuple[Callable[[random.Random], Draft], str, str], ...] = (
    (_arithmetic, "Order of operations", "Evaluate expressions using the order of operations"),
    (_percent, "Percentages", "Calculate a percentage of a quantity"),
    (_linear, "Linear equations", "Solve one-variable linear equations"),
    (_rectangle, "Area and perimeter", "Calculate the area and perimeter of rectangles"),
    (_fractions, "Fractions", "Add fractions with different denominators"),
    (_mean, "Averages", "Calculate the mean of a list of numbers"),
)


def _assemble(draft: Draft, rng: random.Random) -> tuple[dict[str, str], str] | None:
    """Four distinct options with the key at a seeded position; ``None`` if three distractors cannot be found."""
    _, key, candidates, _ = draft
    distinct: list[Fraction] = []
    for value in [*candidates, key + 1, key - 1, key * 2]:
        if value != key and value not in distinct:
            distinct.append(value)
    if len(distinct) < 3:
        return None
    position = rng.randrange(len(OPTION_KEYS))
    texts = [fmt(v) for v in distinct[:3]]
    texts.insert(position, fmt(key))
    return dict(zip(OPTION_KEYS, texts, strict=True)), OPTION_KEYS[position]


def build_math_questions(seed: int = SEED, per_family: int = PER_FAMILY) -> list[EvalQuestion]:
    """Distinct clean questions, deterministic for a seed. Dedupes on stem."""
    rng = random.Random(seed)
    seen: set[str] = set()
    questions: list[EvalQuestion] = []
    for build, subtopic, objective in _FAMILIES:
        for _ in range(per_family):
            for _attempt in range(_MAX_ATTEMPTS):
                draft = build(rng)
                assembled = _assemble(draft, rng)
                if assembled is not None and draft[0] not in seen:
                    break
            else:
                raise RuntimeError(f"could not build {per_family} distinct questions for {subtopic}")
            seen.add(draft[0])
            options, answer = assembled
            n = len(questions)
            band = _BANDS[(n // 3) % 3]
            questions.append(
                EvalQuestion(
                    id=f"calib-math-{n + 1:04d}",
                    subject_code=SUBJECT_CODE,
                    grade_level=6 + n % 3,
                    subtopic_name=subtopic,
                    learning_objective=objective,
                    difficulty_band=band,
                    difficulty_level=_LEVELS[band],
                    question_text=draft[0],
                    options=options,
                    correct_answer=answer,
                    explanation=draft[3],
                )
            )
    return questions
