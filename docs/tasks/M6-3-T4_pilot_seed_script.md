# M6-3-T4 — Pilot School Seed Script
**Milestone:** M6 · **Epic:** M6-3 · **Task:** T4
**Depends on:** All prior M6 tasks complete — billing, rate limiting, error handling all active
**Blocks:** M6-3-T5 (pre-launch checklist uses this script)
**Estimated effort:** 2–3 hours

---

## Context

This script creates the real Bali pilot school in the production database. It runs
exactly once. It is idempotent — if run a second time, it detects that the school
already exists (by slug) and exits cleanly without creating duplicates. It must not
be run in the development or staging environment — add an explicit `ENVIRONMENT`
check that aborts if `ENVIRONMENT != "production"`.

The script does not invent school names or contact details. All real school names,
teacher names, and contact information come from Vibhu directly before this script
is run. The script uses placeholder values that must be replaced before execution.

---

## User Story

As the Kaihle team, we want to create the Bali pilot school account with all necessary
users so the school can start using the platform on day one.

---

## Files to Create

```
backend/scripts/seed_pilot_school.py   ← CREATE
backend/tests/unit/test_seed_pilot_school.py ← CREATE (tests the idempotency logic only)
```

---

## Script Structure

```python
#!/usr/bin/env python
"""Seed the Bali pilot school in the production database.

USAGE:
    ENVIRONMENT=production python scripts/seed_pilot_school.py

This script is idempotent. Running it a second time will detect the existing
school and exit without making any changes.

BEFORE RUNNING: Replace all PLACEHOLDER_ values with real data from Vibhu.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Safety guard — abort if not running against production
if os.environ.get("ENVIRONMENT") != "production":
    print("ERROR: This script must only run against the production database.")
    print(f"Current ENVIRONMENT={os.environ.get('ENVIRONMENT', 'not set')}")
    sys.exit(1)
```

The script creates the following entities in this order. Each step is wrapped in a
try/except and logs clearly to stdout.

**Step 1 — Check for existing school.** Query by slug. If found, print
"Pilot school already exists — skipping." and exit 0. This is the idempotency guard.

**Step 2 — Create the school.**

```python
school_data = {
    "name": "PLACEHOLDER_SCHOOL_NAME",
    "slug": "bali-pilot",   # keep this fixed — it is the idempotency key
    "country": "ID",
    "timezone": "Asia/Makassar",
    "status": "active",
}
```

**Step 3 — Create the school subscription.** Tier: TRIAL. Trial start: today.

**Step 4 — Create the School Admin user.**

```python
admin_data = {
    "email": "PLACEHOLDER_ADMIN_EMAIL",
    "first_name": "PLACEHOLDER_FIRST_NAME",
    "last_name": "PLACEHOLDER_LAST_NAME",
    "role": "SCHOOL_ADMIN",
}
```

Do not set a password here. Send a magic link to the admin's email immediately after
creation so they can set their password when they first log in.

**Step 5 — Create teacher accounts.** One entry per teacher. Same magic-link pattern.

```python
teachers = [
    {"email": "PLACEHOLDER_TEACHER_1_EMAIL", "first_name": "PLACEHOLDER", "last_name": "PLACEHOLDER"},
    {"email": "PLACEHOLDER_TEACHER_2_EMAIL", "first_name": "PLACEHOLDER", "last_name": "PLACEHOLDER"},
]
```

**Step 6 — Print a summary.** After all entities are created, print a clear summary:

```
✅ Pilot school seeded successfully
   School: PLACEHOLDER_SCHOOL_NAME
   School Admin: PLACEHOLDER_ADMIN_EMAIL
   Teachers created: 2
   Magic links sent to all new accounts
   
Next steps:
  1. School admin receives email and sets password
  2. School admin creates grade/subject classes
  3. School admin invites students
  4. Students complete onboarding
```

---

## Acceptance Criteria

**Unit tests — `test_seed_pilot_school.py`** (these test the idempotency logic only,
not the real production data)

`test_script_exits_when_environment_not_production` — Call the script with
`ENVIRONMENT=development`. Assert it exits with a non-zero status code and prints the
safety guard message.

`test_script_exits_cleanly_when_school_already_exists` — Seed a school with slug
`bali-pilot`. Run the seed function. Assert it exits with code 0 and prints the
"already exists — skipping" message without attempting to create the school again.

`test_script_creates_school_when_slug_not_found` — Call the seed function against an
empty test DB. Assert a `School` row exists with `slug == "bali-pilot"` after the
function returns.

**Manual verification before running in production.** Replace all `PLACEHOLDER_` values
with real data from Vibhu. Run the script against the staging database first. Verify
all entities are created and magic link emails are received. Then run against production.

---

## Do NOT Touch

Any existing migration file. Any existing seed script. The `scripts/` directory is
for one-off operational scripts only — do not import from it in application code.
