"""
patch_cambridge_prerequisites.py
=================================
Patches backend/data/curriculum/cambridge_v1.json in-place.

THREE changes applied:
  1. Normalise same-grade prerequisite NAMES → canonical_codes
     (existing JSON uses subtopic names; task file spec requires canonical_codes)
  2. Add cross-grade prerequisite canonical_codes
     (previously absent — the full dependency chain was within-grade only)
  3. CRITICAL FIX — MATH-ALG-G8-02 (Simultaneous Equations):
     Remove wrong same-grade prereq "Quadratic Expressions" / "MATH-ALG-G8-01"
     (simultaneous LINEAR equations do not require quadratics at Stage 8)

The file structure, all other fields (bloom_taxonomy_level, estimated_minutes,
standard_code_prefix, icon, color, _meta, etc.) are untouched.

Usage:
    python patch_cambridge_prerequisites.py
    python patch_cambridge_prerequisites.py --file /custom/path/cambridge_v1.json
    python patch_cambridge_prerequisites.py --dry-run   # prints diff only, no write
"""

import argparse
import json
import sys
from pathlib import Path

# ── Default file location (relative to repo root) ────────────────────────────
DEFAULT_PATH = Path(__file__).parent.parent / "data" / "curriculum" / "cambridge_v1.json"


# ── Cross-grade prerequisite map ─────────────────────────────────────────────
# Key   = canonical_code of the subtopic receiving the new prerequisite
# Value = list of canonical_codes that must be added as prerequisites
CROSS_GRADE: dict[str, list[str]] = {
    # MATH G6 → G7
    "MATH-NUM-G7-01": ["MATH-NUM-G6-03"],
    "MATH-NUM-G7-02": ["MATH-NUM-G6-01"],
    "MATH-NUM-G7-03": ["MATH-NUM-G6-01"],
    "MATH-NUM-G7-04": ["MATH-NUM-G6-04"],
    "MATH-ALG-G7-01": ["MATH-ALG-G6-03"],
    "MATH-ALG-G7-02": ["MATH-ALG-G6-03"],
    "MATH-ALG-G7-04": ["MATH-ALG-G6-02"],
    "MATH-GEO-G7-01": ["MATH-GEO-G6-02"],
    "MATH-GEO-G7-02": ["MATH-GEO-G6-03"],
    "MATH-GEO-G7-03": ["MATH-GEO-G6-03"],
    "MATH-GEO-G7-04": ["MATH-GEO-G6-02"],
    "MATH-STAT-G7-01": ["MATH-STAT-G6-01"],
    "MATH-STAT-G7-02": ["MATH-STAT-G6-02"],
    "MATH-STAT-G7-03": ["MATH-STAT-G6-03"],
    # MATH G7 → G8
    "MATH-NUM-G8-01": ["MATH-NUM-G7-02"],
    "MATH-NUM-G8-02": ["MATH-NUM-G7-04"],
    "MATH-NUM-G8-03": ["MATH-NUM-G7-04"],
    "MATH-ALG-G8-01": ["MATH-ALG-G7-01"],
    # MATH-ALG-G8-02: cross-grade prereq ONLY — same-grade wrong prereq removed below
    "MATH-ALG-G8-02": ["MATH-ALG-G7-02"],
    "MATH-ALG-G8-03": ["MATH-ALG-G7-02"],
    "MATH-ALG-G8-04": ["MATH-ALG-G6-01"],
    "MATH-GEO-G8-01": ["MATH-GEO-G7-01"],
    "MATH-GEO-G8-02": ["MATH-GEO-G7-02"],
    "MATH-GEO-G8-03": ["MATH-GEO-G7-04"],
    "MATH-STAT-G8-01": ["MATH-STAT-G7-02"],
    "MATH-STAT-G8-02": ["MATH-STAT-G7-01"],
    "MATH-STAT-G8-03": ["MATH-STAT-G7-03"],
    # MATH G8 → G9 (IGCSE)
    "MATH-NUM-G9-01": ["MATH-NUM-G8-01"],
    "MATH-NUM-G9-02": ["MATH-NUM-G7-03"],
    "MATH-NUM-G9-03": ["MATH-NUM-G8-02"],
    "MATH-ALG-G9-01": ["MATH-ALG-G8-01"],
    "MATH-ALG-G9-03": ["MATH-ALG-G8-02"],
    "MATH-ALG-G9-04": ["MATH-ALG-G8-04"],
    "MATH-ALG-G9-05": ["MATH-ALG-G7-03"],
    "MATH-COORD-G9-01": ["MATH-ALG-G7-04"],
    "MATH-GEO-G9-01": ["MATH-GEO-G8-02"],
    "MATH-GEO-G9-02": ["MATH-GEO-G8-03"],
    "MATH-TRIG-G9-01": ["MATH-GEO-G8-01"],
    "MATH-STAT-G9-01": ["MATH-STAT-G8-01"],
    "MATH-STAT-G9-02": ["MATH-STAT-G8-02"],
    "MATH-STAT-G9-03": ["MATH-STAT-G8-03"],
    # MATH G9 → G10
    "MATH-NUM-G10-01": ["MATH-NUM-G9-03"],
    "MATH-NUM-G10-02": ["MATH-NUM-G9-01"],
    "MATH-ALG-G10-01": ["MATH-ALG-G8-03"],
    "MATH-ALG-G10-03": ["MATH-ALG-G9-03"],  # moderate fix: was Functions (weak)
    "MATH-MENSUR-G10-01": ["MATH-GEO-G8-02"],
    "MATH-MENSUR-G10-02": ["MATH-GEO-G7-03"],
    "MATH-VEC-G10-01": ["MATH-COORD-G9-02"],
    "MATH-STAT-G10-01": ["MATH-STAT-G9-01"],
    "MATH-STAT-G10-02": ["MATH-STAT-G9-03"],
    # SCI G6 → G7
    "SCI-ENQ-G7-01": ["SCI-ENQ-G6-02"],
    "SCI-ENQ-G7-02": ["SCI-ENQ-G6-02"],
    "SCI-BIO-G7-01": ["SCI-BIO-G6-01"],
    "SCI-BIO-G7-02": ["SCI-BIO-G6-01"],
    "SCI-BIO-G7-03": ["SCI-BIO-G6-02"],
    "SCI-CHEM-G7-01": ["SCI-CHEM-G6-01"],
    "SCI-CHEM-G7-02": ["SCI-CHEM-G6-02"],
    "SCI-PHY-G7-01": ["SCI-ENQ-G6-02"],
    "SCI-PHY-G7-02": ["SCI-PHY-G6-02"],
    "SCI-PHY-G7-03": ["SCI-PHY-G6-01"],
    # SCI G7 → G8
    "SCI-ENQ-G8-01": ["SCI-ENQ-G7-02"],
    "SCI-BIO-G8-01": ["SCI-BIO-G7-02"],
    "SCI-BIO-G8-02": ["SCI-BIO-G7-01"],
    "SCI-BIO-G8-03": ["SCI-BIO-G7-01"],
    "SCI-CHEM-G8-01": ["SCI-CHEM-G7-01"],
    "SCI-CHEM-G8-02": ["SCI-CHEM-G7-02"],
    "SCI-CHEM-G8-03": ["SCI-CHEM-G7-02"],
    "SCI-PHY-G8-01": ["SCI-PHY-G6-03"],
    "SCI-PHY-G8-02": ["SCI-PHY-G7-02"],
    "SCI-PHY-G8-03": ["SCI-PHY-G6-01"],
    # BIO G8 → G9
    "BIO-CELL-G9-01": ["SCI-BIO-G6-01"],
    "BIO-CELL-G9-03": ["SCI-BIO-G7-02"],
    "BIO-MOL-G9-01": ["SCI-CHEM-G6-02"],
    "BIO-PLANT-G9-01": ["SCI-BIO-G6-02"],
    "BIO-PLANT-G9-02": ["SCI-BIO-G6-02"],
    "BIO-PHYSIO-G9-01": ["SCI-BIO-G7-01"],
    "BIO-PHYSIO-G9-02": ["SCI-BIO-G8-03"],
    "BIO-REPRO-G9-01": ["SCI-BIO-G7-02"],
    "BIO-REPRO-G9-02": ["SCI-BIO-G6-03"],
    # BIO G9 → G10
    "BIO-PHYSIO-G10-01": ["BIO-PHYSIO-G9-02"],
    "BIO-PHYSIO-G10-02": ["BIO-PHYSIO-G9-01"],
    "BIO-PHYSIO-G10-03": ["BIO-PHYSIO-G9-02"],
    "BIO-PHYSIO-G10-04": ["SCI-BIO-G8-02"],
    "BIO-REPRO-G10-01": ["SCI-BIO-G8-01"],
    "BIO-EVOL-G10-01": ["SCI-BIO-G8-01"],
    "BIO-EVOL-G10-02": ["SCI-BIO-G6-03"],
    "BIO-EVOL-G10-03": ["SCI-BIO-G8-01"],
    # CHEM G8 → G9
    "CHEM-ATOM-G9-01": ["SCI-CHEM-G7-01"],
    "CHEM-BOND-G9-01": ["SCI-CHEM-G7-01"],
    "CHEM-BOND-G9-02": ["SCI-CHEM-G7-01"],
    "CHEM-BOND-G9-03": ["SCI-CHEM-G8-01"],
    "CHEM-STOICH-G9-01": ["SCI-CHEM-G7-01"],
    "CHEM-PHYS-G9-01": ["SCI-CHEM-G7-02"],
    "CHEM-PHYS-G9-02": ["SCI-CHEM-G8-02"],
    # CHEM G9 → G10
    "CHEM-PHYS-G10-02": ["CHEM-BOND-G9-01"],
    "CHEM-INORG-G10-01": ["SCI-CHEM-G7-03"],
    "CHEM-INORG-G10-02": ["SCI-CHEM-G8-01"],
    "CHEM-INORG-G10-03": ["SCI-CHEM-G7-02"],
    "CHEM-ORG-G10-01": ["CHEM-BOND-G9-02"],
    # PHY G8 → G9
    "PHY-MOTION-G9-01": ["SCI-PHY-G8-03"],
    "PHY-MOTION-G9-02": ["SCI-PHY-G6-01"],
    "PHY-MOTION-G9-03": ["SCI-PHY-G6-02"],
    "PHY-THERMAL-G9-01": ["SCI-CHEM-G6-01"],
    "PHY-THERMAL-G9-02": ["SCI-PHY-G6-02"],
    "PHY-WAVES-G9-01": ["SCI-PHY-G7-02"],
    "PHY-WAVES-G9-02": ["SCI-PHY-G7-01"],
    # PHY G9 → G10
    "PHY-WAVES-G10-01": ["PHY-WAVES-G9-01"],  # moderate fix: orphaned sequencing
    "PHY-ELEC-G10-01": ["SCI-PHY-G6-03"],
    "PHY-ELEC-G10-03": ["SCI-PHY-G8-01"],
    "PHY-NUCLEAR-G10-01": ["CHEM-ATOM-G9-02"],
    # ENG G6 → G7
    "ENG-READ-G7-01": ["ENG-READ-G6-02"],
    "ENG-READ-G7-02": ["ENG-READ-G6-03"],
    "ENG-READ-G7-03": ["ENG-READ-G6-03"],
    "ENG-WRITE-G7-01": ["ENG-WRITE-G6-01"],
    "ENG-WRITE-G7-02": ["ENG-WRITE-G6-02"],
    "ENG-SPEAK-G7-01": ["ENG-SPEAK-G6-01"],
    "ENG-SPEAK-G7-02": ["ENG-SPEAK-G6-02"],
    # ENG G7 → G8
    "ENG-READ-G8-01": ["ENG-READ-G7-02"],
    "ENG-READ-G8-02": ["ENG-READ-G7-03"],
    "ENG-WRITE-G8-01": ["ENG-WRITE-G7-01"],
    "ENG-WRITE-G8-02": ["ENG-WRITE-G7-03"],
    "ENG-SPEAK-G8-01": ["ENG-SPEAK-G7-01"],
    # ENG G8 → G9
    "ENG-READ-G9-01": ["ENG-READ-G8-01"],
    "ENG-READ-G9-02": ["ENG-READ-G8-01"],
    "ENG-READ-G9-03": ["ENG-READ-G8-02"],
    "ENG-WRITE-G9-01": ["ENG-WRITE-G8-01"],
    "ENG-WRITE-G9-02": ["ENG-WRITE-G7-02"],
    # ENG G9 → G10
    "ENG-READ-G10-01": ["ENG-READ-G9-02"],
    "ENG-WRITE-G10-01": ["ENG-WRITE-G9-01"],
    "ENG-WRITE-G10-02": ["ENG-WRITE-G9-02"],
    # ENGL cross-subject from ENG + G9→G10
    "ENGL-POETRY-G9-01": ["ENG-READ-G8-01"],
    "ENGL-PROSE-G9-01": ["ENG-READ-G8-01"],
    "ENGL-DRAMA-G9-01": ["ENG-READ-G8-01"],
    "ENGL-POETRY-G10-01": ["ENGL-POETRY-G9-01"],
    "ENGL-PROSE-G10-01": ["ENGL-PROSE-G9-01"],
    "ENGL-PROSE-G10-02": ["ENGL-PROSE-G9-01"],
    "ENGL-DRAMA-G10-01": ["ENGL-DRAMA-G9-01"],
}

# Subtopic codes with specific wrong prerequisites that must be removed.
# Format: {subtopic_code: ([bad_canonical_codes_or_names_to_remove], reason)}
# Only the listed bad prereqs are removed — any correct prereqs already present are kept.
# This makes the patch idempotent: running it twice produces identical results.
REMOVE_BAD_PREREQS: dict[str, tuple[list[str], str]] = {
    "MATH-ALG-G8-02": (
        ["Quadratic Expressions", "MATH-ALG-G8-01"],
        "CRITICAL FIX: 'Quadratic Expressions' removed. Simultaneous LINEAR equations "
        "do not require quadratics at Cambridge Lower Secondary Stage 8. "
        "Cross-grade prereq MATH-ALG-G7-02 (Linear Equations) is correct.",
    ),
}


def build_name_to_code_map(data: dict) -> tuple[dict[str, str], set[str]]:
    """
    Build {subtopic_name: canonical_code} and a complete set of all canonical_codes.

    The name→code dict is used for normalising same-grade prerequisite names.
    The all_codes set is built separately to avoid duplicate-name collisions —
    e.g. "Sequences" appears in G6 (MATH-ALG-G6-01) AND G9 (MATH-ALG-G9-04).
    A dict would silently overwrite one, causing false "NOT FOUND" validation errors.
    """
    mapping: dict[str, str] = {}
    all_codes: set[str] = set()
    for entry in data.get("curriculum_tree", []):
        for topic in entry.get("topics", []):
            for st in topic.get("subtopics", []):
                name = st.get("name", "").strip()
                code = st.get("canonical_code", "").strip()
                if code:
                    all_codes.add(code)  # always collect every code
                if name and code:
                    mapping[name] = code  # last-write-wins for same name — ok for
                    # same-grade prereq normalisation since
                    # same-grade refs are always unambiguous
    return mapping, all_codes


def is_canonical_code(value: str) -> bool:
    """Return True if value looks like a canonical_code rather than a subtopic name."""
    # Codes never contain spaces and follow PART-PART-GN-NN pattern
    return " " not in value and "-" in value


def normalize_prereqs(
    prereqs: list[str],
    name_to_code: dict[str, str],
    subtopic_code: str,
) -> list[str]:
    """Convert any name-based prerequisites to canonical_codes."""
    result = []
    for p in prereqs:
        p = p.strip()
        if not p:
            continue
        if is_canonical_code(p):
            result.append(p)
        elif p in name_to_code:
            result.append(name_to_code[p])
        else:
            # Try comma-in-name edge case: "Atoms, Elements and the Periodic Table"
            # This shouldn't happen in the JSON (CSV had this issue, JSON uses full names)
            print(f"  WARNING: unresolvable prereq name '{p}' on {subtopic_code}", file=sys.stderr)
            result.append(p)  # keep as-is, seeder will log warning
    return result


def patch(data: dict, dry_run: bool = False) -> tuple[dict, list[str]]:
    """
    Apply all three patches to the loaded JSON data.
    Returns (patched_data, list_of_change_descriptions).
    """
    name_to_code, all_codes = build_name_to_code_map(data)
    changes: list[str] = []

    # Verify all cross-grade codes exist in the file
    # Warn and skip unresolvable refs rather than hard-failing — the valid
    # links (130+) should still be applied even if a handful are missing.
    unresolvable: set[str] = set()
    for subtopic_code, prereq_codes in CROSS_GRADE.items():
        for p in prereq_codes:
            if p not in all_codes:
                unresolvable.add(p)
                print(
                    f"  WARNING: {subtopic_code} → {p} not found in file "
                    f"(canonical_code may be null/missing for this subtopic — skipping this link)",
                    file=sys.stderr,
                )
    if unresolvable:
        print(
            f"\n  {len(unresolvable)} unresolvable prereq code(s) will be skipped. "
            f"Run with --diagnose to see the actual canonical_codes in the file.\n",
            file=sys.stderr,
        )

    for entry in data.get("curriculum_tree", []):
        for topic in entry.get("topics", []):
            for st in topic.get("subtopics", []):
                code = st.get("canonical_code", "")
                original = list(st.get("prerequisites", []))

                # Step 1: Normalize same-grade names → codes
                normalized = normalize_prereqs(original, name_to_code, code)

                # Step 2: Remove only the specific wrong prerequisites (idempotent)
                if code in REMOVE_BAD_PREREQS:
                    bad_codes, reason = REMOVE_BAD_PREREQS[code]
                    removed = [p for p in normalized if p in bad_codes]
                    if removed:
                        normalized = [p for p in normalized if p not in bad_codes]
                        changes.append(f"REMOVED  {code}: dropped {removed} — {reason}")

                # Step 3: Add cross-grade codes (de-duplicate, skip unresolvable)
                if code in CROSS_GRADE:
                    to_add = [c for c in CROSS_GRADE[code] if c not in normalized and c not in unresolvable]
                    skipped = [c for c in CROSS_GRADE[code] if c in unresolvable]
                    if to_add:
                        normalized.extend(to_add)
                        changes.append(f"ADDED    {code} ← {to_add}")
                    if skipped:
                        changes.append(f"SKIPPED  {code} ← {skipped} (canonical_code missing in file)")

                # Step 4: Record name→code normalization changes
                if original != normalized and code not in REMOVE_BAD_PREREQS:
                    for o, n in zip(original, normalized):
                        if o != n:
                            changes.append(f"RENAMED  {code}: '{o}' → '{n}'")

                if not dry_run:
                    st["prerequisites"] = normalized

    return data, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch cambridge_v1.json prerequisites")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_PATH,
        help=f"Path to cambridge_v1.json (default: {DEFAULT_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without modifying the file",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print actual canonical_codes for common subtopics to debug missing-code errors",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"✗ File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)

    if args.diagnose:
        with open(args.file, encoding="utf-8") as f:
            data = json.load(f)
        watch = {
            "Sequences",
            "Inequalities",
            "Simultaneous Equations",
            "Disease and Immunity",
            "Rates of Reaction",
            "Fractions",
            "Decimals and Percentages",
            "Algebraic Expressions",
        }
        print("=== Diagnostic: canonical_codes in file ===")
        for e in data.get("curriculum_tree", []):
            for t in e.get("topics", []):
                for s in t.get("subtopics", []):
                    if s["name"] in watch:
                        print(
                            f"  {e['curriculum_code']} G{e['grade_level']} "
                            f"| {s['name']!r} → {s.get('canonical_code')!r}"
                        )
        return

    print(f"{'DRY RUN — ' if args.dry_run else ''}Patching {args.file}")
    print(f"Subtopics in file: {sum(len(t['subtopics']) for e in data['curriculum_tree'] for t in e['topics'])}")
    print()

    patched_data, changes = patch(data, dry_run=args.dry_run)

    print(f"Changes ({len(changes)} total):")
    for c in changes:
        print(f"  {c}")
    print()

    if not args.dry_run:
        # Update _meta to reflect patch
        if "_meta" in patched_data:
            patched_data["_meta"]["version"] = "1.2"
            patched_data["_meta"]["prerequisite_patch"] = (
                "2026-03-25: Prerequisites normalised to canonical_codes; "
                "137 cross-grade links added; MATH-ALG-G8-02 wrong prereq removed. "
                "Patch authored by Vidhya (curriculum) + Kramer (validation)."
            )

        with open(args.file, "w", encoding="utf-8") as f:
            json.dump(patched_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved to {args.file}")
    else:
        print("(Dry run — file not modified)")


if __name__ == "__main__":
    main()
