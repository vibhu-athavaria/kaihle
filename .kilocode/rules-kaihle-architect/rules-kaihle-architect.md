## Architecture Constraints (Non-Negotiable)

All decisions must comply with docs/CONSTITUTION.md.
When in doubt about any constraint, read CONSTITUTION.md §4 (Absolute Rules).

DB schema source of truth: kaihle_v2_1_schema.sql
Always read this file before advising on any model, migration, or column work.
If a task file conflicts with kaihle_v2_1_schema.sql — the SQL file wins.

Tech stack is LOCKED — do not suggest alternative frameworks, ORMs, or libraries.
Any suggestion to deviate must be escalated to the human developer, not implemented.