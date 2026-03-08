# Core Rules — Always Active

## Mandatory Reading (in this exact order before ANY change)
1. `AGENTS.md` — engineering governance. MUST read in full. Abort if you cannot comply.
2. `docs/CONSTITUTION.md` §2 (Tech Stack) and §4 (Absolute Rules)
3. Milestone brief for the active milestone
4. The specific task file you are implementing
5. `kaihle_v2_1_schema.sql` — for any task touching DB tables

## Schema Reference
- The correct schema file is `kaihle_v2_1_schema.sql` (v2_1, not v2)
- If a task file column name and the SQL file disagree → SQL file wins (CONSTITUTION §8)

## Hard Stops — Abort Immediately If:
- You are asked to work directly on `main`
- A test would need to be disabled to pass CI
- You cannot resolve a subtopic_id lookup (e.g. M1-1-T1) — log and skip, never fabricate
- Coverage drops below 90% on service files
- `print()` appears anywhere in production code
- A config value would need to be hardcoded

## Environment
- Dev environment MUST be running via `docker compose up -d` before any test run
- Never run backend code outside Docker Compose except for one-off scripts