## Task Context Loading Protocol

For every task, load exactly these 3 files in order:
1. docs/CONSTITUTION.md
2. docs/milestones/M{N}_brief.md  (N = milestone number from task ID)
3. docs/tasks/M{N}/M{N}-{E}-T{T}_{slug}.md  (the specific task file)

Task file naming pattern:
  docs/tasks/M0/M0-1-T1_init_monorepo.md
  docs/tasks/M1/M1-4-T3_gap_state_calculation.md

NEVER load: kaihle_product_plan_v2_1.md or kaihle_product_plan_v2_REFERENCE.md

## Delegation Rules

Delegate to kaihle-architect (Claude) if ANY of these are true:
  - Acceptance criteria are ambiguous or contradictory
  - Task touches DB schema and migration logic needs review
  - A test is failing and root cause is unclear
  - Developer explicitly asks for a plan first

Delegate directly to kaihle-coder (MiniMax) if ALL of these are true:
  - Task file is fully self-contained and unambiguous
  - All prior task dependencies are confirmed complete
  - No new schema design needed (schema already in kaihle_v2_1_schema.sql)