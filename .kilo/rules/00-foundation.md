# Foundation Rule — Load Before Every Task

## Mandatory Pre-Task Reading

Before making any changes to any file in this repository, you MUST read:

1. `CONSTITUTION.md` — §2 (Tech Stack) and §4 (Absolute Rules) at minimum. Full document preferred.
2. `AGENTS.md` — Engineering governance rules. All MUST/MUST NOT directives are non-negotiable.

Do not proceed past planning until both documents have been read in this session.

## Approval Gate

You MUST NOT write, modify, or delete any code, schema, config, or migration file
without explicit, unambiguous approval from the user.

The correct sequence for every task:
1. Read CONSTITUTION.md and AGENTS.md
2. Analyse the task — identify risks, dependencies, affected files
3. Present your plan to the user
4. **WAIT** for the user to say "proceed", "yes", "go ahead", or equivalent
5. Only then implement

"Analyse and tell me what you'd do" is NOT approval to implement.
"What would this look like?" is NOT approval to implement.
If in doubt, ask. Never assume.

## Where Things Live

| What you need | Where |
|---|---|
| DB schema (columns, indexes) | `kaihle_v2_1_schema.sql` |
| Product plan + milestone goals | `docs/kaihle_product_plan.md` |
| This milestone's brief | `docs/milestones/M{N}_brief.md` |
| This task's instructions | `docs/tasks/M{N}/M{N}-{E}-T{N}_*.md` |
| Design tokens, role specs | `docs/design/DESIGN_SYSTEM.md` |
| API endpoint status | `docs/API_ENDPOINT_TASK_MAP.md` |
| Architecture decisions | `docs/adr/ADR-*.md` |
