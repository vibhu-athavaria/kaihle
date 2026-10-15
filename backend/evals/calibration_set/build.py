"""Build and load the shipped calibration set: ``python -m evals.calibration_set.build``.

Output is byte-identical for a given ``SEED``: seeded sampling, sorted keys, fixed line order (clean
cases, then each defect in ``DEFECTS`` order). Maths only, ``label_source="computed"``; the ground
truth is the ``must_fail`` / ``must_pass`` lists derived by code, never a model judgement.
Each mutated case also records ``must_pass_sample``: the 2 seeded cross-talk criteria to schedule.
"""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evals.calibration_set.math_templates import SEED, build_math_questions
from evals.calibration_set.mutations import DEFECTS, MUTATIONS, MutationRecord, clean_record
from evals.question_model import EvalQuestion

SHIPPED_PATH = Path(__file__).resolve().parent.parent / "datasets" / "question_calibration.jsonl"
CASES_PER_DEFECT = 20
CROSSTALK_SAMPLE = 2
LABEL_SOURCE = "computed"


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    source_id: str
    defect: str | None
    label_source: str
    subset: str
    question: EvalQuestion
    must_fail: tuple[str, ...]
    must_pass: tuple[str, ...]
    must_pass_sample: tuple[str, ...]


def _case(case_id: str, question: EvalQuestion, source_id: str, record: MutationRecord) -> dict[str, Any]:
    rng = random.Random(f"{SEED}:{case_id}:crosstalk")
    sample = sorted(rng.sample(record.must_pass, CROSSTALK_SAMPLE)) if record.defect else []
    return {
        "case_id": case_id,
        "source_id": source_id,
        "defect": record.defect,
        "label_source": LABEL_SOURCE,
        "subset": "computed",
        "question": asdict(question),
        "must_fail": list(record.must_fail),
        "must_pass": list(record.must_pass),
        "must_pass_sample": sample,
    }


def build_calibration_records() -> list[dict[str, Any]]:
    clean = build_math_questions()
    records = [_case(q.id, q, q.id, clean_record(q)) for q in clean]
    for defect in DEFECTS:
        rng = random.Random(f"{SEED}:{defect}")
        for index in sorted(rng.sample(range(len(clean)), CASES_PER_DEFECT)):
            source = clean[index]
            mutated, record = MUTATIONS[defect](source)
            records.append(_case(f"{source.id}~{defect}", mutated, source.id, record))
    return records


def write_calibration_set(path: Path = SHIPPED_PATH) -> Path:
    """Side effect: writes ``path``. Bytes are written directly so newline translation cannot vary."""
    lines = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in build_calibration_records()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def load_calibration_cases(path: Path = SHIPPED_PATH) -> list[CalibrationCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        data = json.loads(line)
        cases.append(
            CalibrationCase(
                case_id=data["case_id"],
                source_id=data["source_id"],
                defect=data["defect"],
                label_source=data["label_source"],
                subset=data["subset"],
                question=EvalQuestion(**data["question"]),
                must_fail=tuple(data["must_fail"]),
                must_pass=tuple(data["must_pass"]),
                must_pass_sample=tuple(data["must_pass_sample"]),
            )
        )
    return cases


if __name__ == "__main__":
    print(f"wrote {write_calibration_set()}")
