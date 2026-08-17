"""Check docs/kaihle_v2_1_schema.sql against the live database.

CONSTITUTION Rule 8 makes that file the source of truth, but nothing enforced it — the
objective layer drifted out of it entirely for months, and a partial index sat
documented as a full one. This compares the two mechanically.

Checks per table: column names, nullability, named CHECK/UNIQUE constraints, index
definitions INCLUDING partial WHERE clauses, and foreign-key targets.

Comparing index *names* alone is not enough. That is exactly how
ix_question_bank_replaces_question_id passed while being partial in the database and
documented as full — the name matched, the semantics did not.

Usage (from backend/, with the stack up):
    python -m scripts.verify_schema_doc
    python -m scripts.verify_schema_doc --tables learning_objectives,question_bank
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DOC = _REPO_ROOT / "docs" / "kaihle_v2_1_schema.sql"

# The tables this file is currently reconciled for. The rest of the document has never
# been verified; widen deliberately rather than assuming silence means agreement.
DEFAULT_TABLES = (
    "learning_objectives",
    "subtopic_objectives",
    "lo_review_items",
    "question_bank",
)


def psql(query: str) -> list[str]:
    """Run a query in the postgres container and return non-empty result lines."""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "kaihle", "-d", "kaihle", "-tA", "-c", query],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def check_table(table: str, doc: str, flat_doc: str) -> list[str]:
    """Return a list of drift descriptions for one table. Empty means it matches."""
    problems: list[str] = []

    body_match = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", doc, re.S)
    if body_match is None:
        return [f"{table}: not present in {SCHEMA_DOC.name}"]
    # Strip trailing -- comments. Without this a declaration ending in
    # "VECTOR(768),  -- some note" has no comma at end-of-line, so the column regex
    # runs on into the NEXT line and inherits its NOT NULL.
    body = re.sub(r"\s*--[^\n]*", "", body_match.group(1))

    # Columns and nullability
    documented_cols = set(re.findall(r"^\s{4}([a-z_]+)\s+\S", body, re.M))
    live_cols: dict[str, str] = {}
    for row in psql(
        f"SELECT column_name||'|'||is_nullable FROM information_schema.columns WHERE table_name='{table}';"
    ):
        name, nullable = row.split("|")
        live_cols[name] = nullable

    for missing in sorted(set(live_cols) - documented_cols):
        problems.append(f"{table}.{missing}: in database, absent from doc")
    for extra in sorted(documented_cols - set(live_cols)):
        problems.append(f"{table}.{extra}: in doc, absent from database")

    for column, nullable in sorted(live_cols.items()):
        if column not in documented_cols:
            continue
        decl = re.search(rf"^\s{{4}}{column}\s+(.*?)(?:,\s*$)", body, re.M | re.S)
        declaration = decl.group(1) if decl else ""
        # PRIMARY KEY implies NOT NULL; the doc does not spell both out.
        doc_not_null = "NOT NULL" in declaration or "PRIMARY KEY" in declaration
        if (nullable == "NO") != doc_not_null:
            problems.append(
                f"{table}.{column}: db_nullable={nullable} but doc {'has' if doc_not_null else 'lacks'} NOT NULL"
            )

    # Named CHECK / UNIQUE constraints
    for conname in psql(
        f"SELECT conname FROM pg_constraint WHERE conrelid='{table}'::regclass AND contype IN ('c','u');"
    ):
        if conname.endswith("_not_null"):
            continue
        if conname not in doc:
            problems.append(f"{table}.{conname}: constraint absent from doc")

    # Indexes — definition, not just name. A UNIQUE constraint is backed by an index of
    # the same name; those are documented as CONSTRAINT ... UNIQUE inside CREATE TABLE,
    # so match either form.
    constraint_names = set(
        psql(f"SELECT conname FROM pg_constraint WHERE conrelid='{table}'::regclass AND contype IN ('p','u');")
    )
    for row in psql(f"SELECT indexname||'|'||indexdef FROM pg_indexes WHERE tablename='{table}';"):
        name, definition = row.split("|", 1)
        if name.endswith("_pkey") or name in constraint_names:
            continue
        documented = re.search(rf"CREATE (?:UNIQUE )?INDEX {re.escape(name)}\b(.*?);", flat_doc, re.I)
        if documented is None:
            problems.append(f"{table}.{name}: index absent from doc")
            continue
        if ("WHERE" in definition.upper()) != ("WHERE" in documented.group(1).upper()):
            problems.append(
                f"{table}.{name}: partial-index mismatch "
                f"(db {'partial' if 'WHERE' in definition.upper() else 'full'}, doc the other)"
            )

    # Foreign-key targets — written inline as REFERENCES, so check the target table.
    for row in psql(
        f"""SELECT a.attname||'|'||cl.relname FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
            JOIN pg_class cl ON cl.oid=c.confrelid
            WHERE c.conrelid='{table}'::regclass AND c.contype='f';"""
    ):
        column, target = row.split("|", 1)
        decl = re.search(rf"^\s{{4}}{column}\s+(.*?)(?:,\s*$)", body, re.M | re.S)
        if decl is None or f"REFERENCES {target}" not in decl.group(1):
            problems.append(f"{table}.{column}: FK -> {target} missing or wrong in doc")

    return problems


def main(tables: tuple[str, ...]) -> int:
    doc = SCHEMA_DOC.read_text()
    flat_doc = re.sub(r"\s+", " ", doc)  # so multi-line CREATE INDEX compares cleanly

    all_problems: list[str] = []
    for table in tables:
        problems = check_table(table, doc, flat_doc)
        all_problems.extend(problems)
        print(f"{'DRIFT' if problems else 'OK   '}  {table}")
        for problem in problems:
            print(f"         {problem}")

    if all_problems:
        print(f"\n{len(all_problems)} discrepancies. {SCHEMA_DOC.name} is the source of truth (Rule 8) — fix it.")
        return 1
    print(f"\nAll {len(tables)} tables match the live database.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help=f"Comma-separated tables to check (default: {','.join(DEFAULT_TABLES)})",
    )
    args = parser.parse_args()
    sys.exit(main(tuple(t.strip() for t in args.tables.split(",") if t.strip())))
