"""
generate_subtopic_mapping.py

Uses an LLM via OpenRouter to semantically map question bank subtopic names
to canonical codes in cambridge_v1.json. Produces subtopic_mapping.json
used by import_questions.py.

Usage:
    pip install openai

    OPENROUTER_API_KEY=your_key python generate_subtopic_mapping.py \
        --questions questions.json \
        --curriculum backend/data/curriculum/cambridge_v1.json \
        --output backend/data/subtopic_mapping.json

    # Choose a different model:
    python generate_subtopic_mapping.py ... --model mistralai/mistral-7b-instruct

    # Resume interrupted run (skips already-mapped keys):
    python generate_subtopic_mapping.py ... --resume

    # Dry run — print mappings without saving:
    python generate_subtopic_mapping.py ... --dry-run

Recommended free/cheap models on OpenRouter:
    mistralai/mistral-7b-instruct       (free tier available)
    google/gemini-flash-1.5             (fast, cheap)
    meta-llama/llama-3.1-8b-instruct    (free tier available)
    anthropic/claude-3-haiku            (cheap, high accuracy)
    qwen/qwen-2.5-7b-instruct           (free tier available)

Output format (subtopic_mapping.json):
    {
      "cambridge_primary/ENG/5/Reading/Develop broad reading skills": "ENG-READ-G5-01",
      "cambridge_lower/MATH/6/Algebra/Write and simplify expressions": "MATH-ALG-G6-02",
      "UNMAPPED": ["cambridge_lower/ENG/6/Reading/Some obscure name", ...]
    }
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

# Regex to extract canonical codes like MATH-NUM-G5-01, ENG-READ-G7-02 etc.
# Handles model responses that include explanation text around the code.
CANONICAL_CODE_RE = re.compile(r"\b([A-Z]+-[A-Z]+-G\d+-\d+)\b")

# ---------------------------------------------------------------------------
# Build curriculum index from cambridge_v1.json
# ---------------------------------------------------------------------------


def build_curriculum_index(curriculum_data: dict) -> dict:
    """
    Extract all subtopics from cambridge_v1.json into a flat index.

    Returns:
        {
          "canonical_code": {
              "name": str,
              "learning_objective": str,
              "topic_name": str,
              "topic_canonical_code": str,
              "subject_code": str,
              "grade_level": int,
              "curriculum_code": str,
          },
          ...
        }
    """
    index = {}
    for entry in curriculum_data.get("curriculum_tree", []):
        curriculum_code = entry["curriculum_code"]
        subject_code = entry["subject_code"]
        grade_level = entry["grade_level"]

        for topic in entry.get("topics", []):
            topic_name = topic["name"]
            topic_canonical = topic["canonical_code"]

            for subtopic in topic.get("subtopics", []):
                code = subtopic["canonical_code"]
                index[code] = {
                    "name": subtopic["name"],
                    "learning_objective": subtopic.get("learning_objective", ""),
                    "topic_name": topic_name,
                    "topic_canonical_code": topic_canonical,
                    "subject_code": subject_code,
                    "grade_level": grade_level,
                    "curriculum_code": curriculum_code,
                }
    return index


def get_candidates_for_question(
    curriculum_index: dict,
    grade_level: int,
    subject_name: str,
    topic_name: str,
) -> list[dict]:
    """
    Filter curriculum_index to subtopics that are plausible matches
    for a given grade/subject/topic combination.

    Filters by:
      - grade_level (exact ±1 grade tolerance for edge cases)
      - subject_code (mapped from subject_name)
      - topic_name (loose match — topic names like 'Number', 'Reading' are stable)

    Returns list of candidate dicts with 'canonical_code' added.
    """
    SUBJECT_NAME_MAP = {
        "Mathematics": "MATH",
        "Math": "MATH",
        "Maths": "MATH",
        "Integrated Science": "SCI",
        "Science": "SCI",
        "English Language": "ENG",
        "English": "ENG",
        "Biology": "BIO",
        "Chemistry": "CHEM",
        "Physics": "PHY",
        "English Literature": "ENGL",
    }

    subject_code = SUBJECT_NAME_MAP.get(subject_name) or next(
        (v for k, v in SUBJECT_NAME_MAP.items() if k.lower() == subject_name.lower()),
        None,
    )

    candidates = []
    for code, info in curriculum_index.items():
        # Grade tolerance: exact match or ±1
        if abs(info["grade_level"] - grade_level) > 1:
            continue
        # Subject filter
        if subject_code and info["subject_code"] != subject_code:
            continue
        # Topic name filter — case-insensitive substring match
        if (
            topic_name
            and topic_name.lower() not in info["topic_name"].lower()
            and info["topic_name"].lower() not in topic_name.lower()
        ):
            continue
        candidates.append({"canonical_code": code, **info})

    # If strict filter yields nothing, fall back to grade+subject only
    if not candidates:
        for code, info in curriculum_index.items():
            if abs(info["grade_level"] - grade_level) > 1:
                continue
            if subject_code and info["subject_code"] != subject_code:
                continue
            candidates.append({"canonical_code": code, **info})

    return candidates


def format_candidates_for_prompt(candidates: list[dict]) -> str:
    """Format candidate subtopics as a numbered list for the LLM prompt."""
    lines = []
    for i, c in enumerate(candidates, 1):
        lines.append(
            f'{i}. [{c["canonical_code"]}] "{c["name"]}" '
            f"(Grade {c['grade_level']}, {c['topic_name']})\n"
            f"   Learning objective: {c['learning_objective']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude mapping call
# ---------------------------------------------------------------------------


async def map_single_combination(
    client: OpenAI,
    model: str,
    combo: dict,
    candidates: list[dict],
    debug_log: list[dict] | None = None,
) -> tuple[str, str | None]:
    """
    Ask the LLM to pick the best canonical code for a single question combo.

    Returns (mapping_key, canonical_code | None).
    canonical_code is None if the model cannot confidently match.
    debug_log: if provided, appends a dict with the raw model output for every call.
    """
    mapping_key = (
        f"{combo['inferred_curriculum']}/{combo['subject_name']}/"
        f"{combo['grade_level']}/{combo['topic_name']}/{combo['subtopic_name']}"
    )

    if not candidates:
        if debug_log is not None:
            debug_log.append(
                {
                    "key": mapping_key,
                    "raw_response": None,
                    "result": "UNMAPPED",
                    "reason": "no_candidates",
                }
            )
        return mapping_key, None

    candidates_text = format_candidates_for_prompt(candidates)

    prompt = f"""You are a Cambridge curriculum specialist mapping question bank entries to Cambridge curriculum subtopics.

QUESTION BANK ENTRY:
- Grade: {combo["grade_level"]}
- Subject: {combo["subject_name"]}
- Topic: {combo["topic_name"]}
- Subtopic: "{combo["subtopic_name"]}"

CAMBRIDGE SUBTOPICS TO CHOOSE FROM:
{candidates_text}

Which Cambridge subtopic best matches the question bank subtopic above?
Focus on conceptual match — what the questions test vs what the Cambridge unit covers.

Reply with ONLY the canonical code (e.g. MATH-NUM-G5-01) if you are confident, or UNMAPPED if nothing fits.
Do not explain. Do not add punctuation. Just the code or UNMAPPED."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content or ""
        valid_codes = {c["canonical_code"] for c in candidates}

        # Extract canonical code via regex — handles model output that includes
        # explanation text, thinking tokens, trailing punctuation etc.
        # Module-level CANONICAL_CODE_RE pattern: e.g. MATH-NUM-G6-03, ENG-READ-G5-01
        matches = CANONICAL_CODE_RE.findall(raw.upper())
        for match in matches:
            if match in valid_codes:
                if debug_log is not None:
                    debug_log.append(
                        {
                            "key": mapping_key,
                            "raw_response": raw,
                            "result": match,
                            "reason": "regex_extracted",
                        }
                    )
                return mapping_key, match

        # Check for explicit UNMAPPED signal
        if "UNMAPPED" in raw.upper():
            if debug_log is not None:
                debug_log.append(
                    {
                        "key": mapping_key,
                        "raw_response": raw,
                        "result": "UNMAPPED",
                        "reason": "model_said_unmapped",
                    }
                )
            return mapping_key, None

        # Nothing matched — log the raw output so we can inspect it
        if debug_log is not None:
            debug_log.append(
                {
                    "key": mapping_key,
                    "raw_response": raw,
                    "result": "UNMAPPED",
                    "reason": "no_valid_code_extracted",
                    "candidates": [c["canonical_code"] for c in candidates],
                }
            )
        return mapping_key, None

    except Exception as e:
        if debug_log is not None:
            debug_log.append(
                {
                    "key": mapping_key,
                    "raw_response": None,
                    "result": "UNMAPPED",
                    "reason": f"api_error: {e}",
                }
            )
        print(f"  API error for '{combo['subtopic_name']}': {e}", file=sys.stderr)
        return mapping_key, None


# ---------------------------------------------------------------------------
# Extract unique combinations from questions JSON
# ---------------------------------------------------------------------------


def extract_unique_combinations(questions_data: list[dict]) -> list[dict]:
    """Extract unique (grade, subject, topic, subtopic) combinations with question counts."""
    SUBJECT_NAME_MAP = {
        "Mathematics": "MATH",
        "Math": "MATH",
        "Maths": "MATH",
        "Integrated Science": "SCI",
        "Science": "SCI",
        "English Language": "ENG",
        "English": "ENG",
        "Biology": "BIO",
        "Chemistry": "CHEM",
        "Physics": "PHY",
        "English Literature": "ENGL",
    }

    def infer_curriculum(grade_level: int) -> str:
        if grade_level == 5:
            return "cambridge_primary"
        elif 6 <= grade_level <= 8:
            return "cambridge_lower"
        elif 9 <= grade_level <= 10:
            return "igcse"
        return "unknown"

    seen: dict[tuple, dict] = {}
    for q in questions_data:
        grade = q.get("grade_level")
        subject = q.get("subject_name", "")
        topic = q.get("topic_name", "")
        subtopic = q.get("subtopic_name", "")
        key = (grade, subject, topic, subtopic)

        if key not in seen:
            seen[key] = {
                "grade_level": grade,
                "subject_name": subject,
                "topic_name": topic,
                "subtopic_name": subtopic,
                "inferred_curriculum": infer_curriculum(grade),
                "inferred_subject_code": SUBJECT_NAME_MAP.get(subject, subject),
                "question_count": 0,
            }
        seen[key]["question_count"] += 1

    return list(seen.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(
    questions_path: Path,
    curriculum_path: Path,
    output_path: Path,
    model: str,
    base_url: str | None,
    api_key: str | None,
    resume: bool,
    dry_run: bool,
    rate_limit_delay: float,
) -> None:
    # Load inputs
    print(f"Loading questions from {questions_path}...")
    with open(questions_path) as f:
        raw = json.load(f)
    questions_data = raw["questions"] if isinstance(raw, dict) and "questions" in raw else raw
    print(f"  {len(questions_data)} questions loaded.")

    print(f"Loading curriculum from {curriculum_path}...")
    with open(curriculum_path) as f:
        curriculum_data = json.load(f)

    curriculum_index = build_curriculum_index(curriculum_data)
    print(f"  {len(curriculum_index)} subtopics indexed from curriculum.")

    # Extract unique combinations
    combos = extract_unique_combinations(questions_data)
    print(f"  {len(combos)} unique (grade/subject/topic/subtopic) combinations.")

    # Load existing mapping if resuming
    existing_mapping: dict[str, str] = {}
    existing_unmapped: list[str] = []

    # Keys that are metadata, not canonical code mappings — must be stripped
    # before building existing_mapping to avoid corrupting the output file.
    METADATA_KEYS = {"UNMAPPED", "NEEDS_REVIEW", "debug"}

    if resume and output_path.exists():
        with open(output_path) as f:
            saved = json.load(f)

        existing_unmapped = saved.get("UNMAPPED", [])

        # Only keep string-valued entries (canonical codes) — strip all metadata keys
        existing_mapping = {k: v for k, v in saved.items() if k not in METADATA_KEYS and isinstance(v, str)}

        print(f"  Resuming — {len(existing_mapping)} already mapped, {len(existing_unmapped)} already unmapped.")

    # Build already_done set from mapping keys.
    # Also normalise stale 'unknown/' prefixes — entries that previously failed
    # because infer_curriculum_code returned None are stored as 'unknown/Subject/Grade/...'
    # but the current run generates keys with the real curriculum prefix (e.g.
    # 'cambridge_as_level/Math/11/...'). Strip the first path segment from UNMAPPED
    # entries so they match regardless of which curriculum prefix was used.
    mapped_keys = set(existing_mapping.keys())
    unmapped_suffixes = set()
    for u in existing_unmapped:
        parts = u.split("/", 1)
        # suffix = everything after the curriculum prefix: "Subject/Grade/Topic/Subtopic"
        if len(parts) == 2:
            unmapped_suffixes.add(parts[1])

    pending = []
    for combo in combos:
        key = (
            f"{combo['inferred_curriculum']}/{combo['subject_name']}/"
            f"{combo['grade_level']}/{combo['topic_name']}/{combo['subtopic_name']}"
        )
        suffix = f"{combo['subject_name']}/{combo['grade_level']}/{combo['topic_name']}/{combo['subtopic_name']}"
        if key in mapped_keys or suffix in unmapped_suffixes:
            continue
        pending.append(combo)

    print(f"  {len(pending)} combinations to process.")

    if not pending:
        print("Nothing to do — all combinations already mapped.")
        return

    # ── LLM client setup ─────────────────────────────────────────────────
    #
    # Priority order:
    #   1. --base-url set → private vLLM server
    #   2. --base-url not set → OpenRouter
    #
    # API key resolution (same priority for both providers):
    #   1. --api-key argument
    #   2. OPENROUTER_API_KEY env var  (OpenRouter)
    #   3. VLLM_API_KEY env var        (vLLM)
    #   4. "EMPTY" string              (vLLM with no auth — still required by openai client)

    if base_url:
        resolved_api_key = api_key or os.environ.get("VLLM_API_KEY") or "EMPTY"
        resolved_base_url = base_url
        print(f"Provider:  vLLM  ({resolved_base_url})")
        print(f"Model:     {model}")
    else:
        resolved_base_url = "https://openrouter.ai/api/v1"
        resolved_api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not resolved_api_key:
            print(
                "ERROR: No API key found.\n"
                "  Pass --api-key YOUR_KEY, or set OPENROUTER_API_KEY env var,\n"
                "  or use --base-url to point at a private vLLM server.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Provider:  OpenRouter  ({resolved_base_url})")
        print(f"Model:     {model}")

    client = OpenAI(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
    )

    # Process each combination
    mapping: dict[str, str] = dict(existing_mapping)  # explicit copy — never mutate existing_mapping
    unmapped: list[str] = list(existing_unmapped)
    debug_log: list[dict] = []

    for i, combo in enumerate(pending, 1):
        candidates = get_candidates_for_question(
            curriculum_index,
            combo["grade_level"],
            combo["subject_name"],
            combo["topic_name"],
        )

        print(
            f"[{i}/{len(pending)}] Grade {combo['grade_level']} "
            f"{combo['subject_name']} / {combo['topic_name']} / "
            f'"{combo["subtopic_name"]}" '
            f"({len(candidates)} candidates, {combo['question_count']}q)..."
        )

        mapping_key, canonical_code = await map_single_combination(
            client, model, combo, candidates, debug_log=debug_log
        )

        if canonical_code:
            print(f"  → {canonical_code}")
            mapping[mapping_key] = canonical_code
        else:
            # Show raw response inline so failures are visible in terminal too
            last = debug_log[-1] if debug_log else {}
            raw_preview = repr(last.get("raw_response", ""))[:80]
            print(f"  → UNMAPPED  (raw: {raw_preview})")
            unmapped.append(mapping_key)

        # Save progress after every 10 mappings (resumable)
        if not dry_run and i % 10 == 0:
            output = {**mapping, "UNMAPPED": unmapped}
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(output, f, indent=2)
            # Write debug log checkpoint
            debug_log_path = output_path.with_suffix(".debug.json")
            with open(debug_log_path, "w") as f:
                json.dump(debug_log, f, indent=2)
            print(f"  [checkpoint saved — {len(mapping)} mapped, {len(unmapped)} unmapped]")

        # Rate limit
        if i < len(pending):
            time.sleep(rate_limit_delay)

    # Final save
    output = {**mapping, "UNMAPPED": unmapped}

    if dry_run:
        print("\n--- DRY RUN OUTPUT (not saved) ---")
        print(json.dumps(output, indent=2)[:2000] + "...")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nMapping saved to {output_path}")

        # Write final debug log
        debug_log_path = output_path.with_suffix(".debug.json")
        with open(debug_log_path, "w") as f:
            json.dump(debug_log, f, indent=2)
        print(f"Debug log saved to {debug_log_path}")

    # Summary
    print("\n" + "=" * 55)
    print("MAPPING COMPLETE")
    print("=" * 55)
    print(f"Total combinations:  {len(combos)}")
    print(f"Successfully mapped: {len(mapping)}")
    print(f"Unmapped:            {len(unmapped)}")
    print(f"Coverage:            {len(mapping) / len(combos) * 100:.1f}%")
    if unmapped:
        print("\nUnmapped entries (review manually):")
        for u in unmapped[:20]:
            print(f"  - {u}")
        if len(unmapped) > 20:
            print(f"  ... and {len(unmapped) - 20} more (see UNMAPPED key in output file)")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate subtopic_mapping.json using LLM semantic matching.\n"
            "Supports OpenRouter (cloud) or a private vLLM server.\n\n"
            "Examples:\n"
            "  # OpenRouter with API key argument:\n"
            "  python generate_subtopic_mapping.py --questions q.json --api-key sk-or-... --model google/gemma-4-26b-a4b-it\n\n"
            "  # OpenRouter with env var:\n"
            "  OPENROUTER_API_KEY=sk-or-... python generate_subtopic_mapping.py --questions q.json\n\n"
            "  # Private vLLM server:\n"
            "  python generate_subtopic_mapping.py --questions q.json --base-url http://192.168.1.100:8000/v1 --model gemma-4-26b-a4b-it\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--questions",
        type=Path,
        required=True,
        help="Path to questions JSON file",
    )
    parser.add_argument(
        "--curriculum",
        type=Path,
        default=Path("backend/data/curriculum/cambridge_v1.json"),
        help="Path to cambridge_v1.json (default: backend/data/curriculum/cambridge_v1.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/data/subtopic_mapping.json"),
        help="Output path for mapping file (default: backend/data/subtopic_mapping.json)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "API key for OpenRouter or vLLM. "
            "Falls back to OPENROUTER_API_KEY or VLLM_API_KEY env vars. "
            "vLLM with no auth defaults to 'EMPTY'."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=("Base URL of a private vLLM server (e.g. http://192.168.1.100:8000/v1). If not set, uses OpenRouter."),
    )
    parser.add_argument(
        "--model",
        default="google/gemma-4-26b-a4b-it",
        help=(
            "Model identifier (default: google/gemma-4-26b-a4b-it). "
            "OpenRouter examples: google/gemini-flash-1.5, mistralai/mistral-7b-instruct, "
            "meta-llama/llama-3.1-8b-instruct. "
            "vLLM: use the --served-model-name from your server startup."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing output file, skipping already-mapped entries",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without saving",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.3,
        help="Seconds to wait between API calls (default: 0.3). Set to 0 for vLLM.",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            questions_path=args.questions,
            curriculum_path=args.curriculum,
            output_path=args.output,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            resume=args.resume,
            dry_run=args.dry_run,
            rate_limit_delay=args.rate_limit_delay,
        )
    )
