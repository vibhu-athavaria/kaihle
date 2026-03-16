# M6-3-T4 — Pilot School Seed Script
**Task ID:** M6-3-T4
**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Readiness
**Depends on:** M0-2-T1 (migrations), M1-2-T1 (curriculum seeding), M1-1-T1 (question import)
**Blocks:** M6-3-T5 (pre-launch checklist)

---

## User Story

As the platform operator, I want a single script that sets up the first Bali pilot school in production with all required data — school record, admin user, curriculum, and question bank — so the pilot can begin without manual database intervention.

---

## Context

Before the first real school goes live, the production database needs to be seeded with:
1. The pilot school record
2. A School Admin user for that school
3. Cambridge curriculum adopted by that school
4. Subscription plan (Trial tier to start)

The curriculum graph and question bank are seeded by **separate scripts** (`seed_curriculum_graph.py` and `import_questions.py`) that must already have been run. This script only sets up the school-specific records.

**This script must be idempotent** — running it twice must produce no duplicates and no errors.

---

## Files to Create

```
backend/scripts/seed_pilot_school.py     CREATE — pilot school setup script
backend/scripts/seed_all_production.py  CREATE — orchestrator that calls all seed scripts in order
```

---

## Implementation Detail

### `seed_pilot_school.py`

```python
"""
Seed script for Bali pilot school.
Run AFTER: seed_curriculum_graph.py and import_questions.py

Usage:
    python -m scripts.seed_pilot_school \
        --school-name "Bali Coding School" \
        --admin-email "admin@balicodingschool.com" \
        --admin-first-name "Wayan" \
        --admin-last-name "Sudarsana"

Environment: reads DATABASE_URL from environment.
Idempotent: safe to run multiple times.
"""
```

**Step-by-step logic:**

1. **Create or fetch school:**
   ```python
   school = await upsert_school(
       name="Bali Coding School",     # from CLI arg
       slug="bali-coding-school",     # auto-derived from name
       timezone="Asia/Makassar",
       country="Indonesia",
       city="Bali"
   )
   # Upsert on slug unique constraint — if exists, return existing
   ```

2. **Adopt curriculum:**
   ```python
   # Fetch Cambridge Lower Secondary and IGCSE from curricula table
   # Upsert into school_curricula for this school
   # Subjects: MATH + SCI + ENG (Lower Secondary), MATH + BIO + CHEM + PHY + ENG + ENGL (IGCSE)
   ```

3. **Create trial subscription:**
   ```python
   # Fetch TRIAL tier from subscription_plans
   # Upsert into school_subscriptions:
   #   status=ACTIVE, billing_cycle=trial
   #   student_count=30 (trial max)
   #   start_date=today, end_date=today+15days
   #   trial_end_date=today+15days
   # Skip if school already has an active subscription
   ```

4. **Create School Admin user:**
   ```python
   admin = await upsert_user(
       email=args.admin_email,        # from CLI arg
       first_name=args.admin_first_name,
       last_name=args.admin_last_name,
       role=UserRole.SCHOOL_ADMIN,
       school_id=school.id,
       is_active=True
   )
   # Upsert on email+school_id — if exists, skip
   # Set a temporary password: "Kaihle2026!" (must be changed on first login)
   # Log the temporary password to console ONLY — never store in code
   ```

5. **Print summary:**
   ```
   ✅ Pilot school seeded successfully

   School:      Bali Coding School (slug: bali-coding-school)
   School ID:   <uuid>
   Curricula:   Cambridge Lower Secondary, IGCSE
   Subjects:    Mathematics, Science, English Language

   Admin User:  Wayan Sudarsana
   Email:       admin@balicodingschool.com
   Temp pass:   Kaihle2026! (must change on first login)

   Subscription: TRIAL (15 days, max 30 students)
   Expires:     <date>

   Next steps:
   1. Email admin their credentials
   2. Admin logs in and changes password
   3. Admin invites teachers
   4. Teachers create classes and enroll students
   ```

### `seed_all_production.py`

Orchestrator that documents and runs the full seed sequence:

```python
"""
Full production seed sequence. Run once on a fresh production database.

Order:
  1. seed_curriculum_graph.py   — populates curricula, subjects, grades, topics, subtopics
  2. import_questions.py        — imports 7,000 questions into question_bank
  3. ingest_curriculum.py       — generates pgvector embeddings (optional, can run after launch)
  4. seed_pilot_school.py       — creates first school, admin, subscription
"""
```

This script does not call the others directly — it just prints the ordered command sequence with instructions. A human runs them manually in order to maintain control over each step.

---

## CLI Usage

```bash
# Step 1 — Run from repo root in production environment
cd backend

# Seed curriculum graph (idempotent)
python -m scripts.seed_curriculum_graph

# Import question bank (idempotent)
python -m scripts.import_questions --file data/questions/kaihle_questions_v1.csv

# Seed pilot school (idempotent)
python -m scripts.seed_pilot_school \
  --school-name "Bali Coding School" \
  --admin-email "admin@balicodingschool.com" \
  --admin-first-name "Wayan" \
  --admin-last-name "Sudarsana"

# Optional — generate embeddings (slow, can run after launch)
python -m scripts.ingest_curriculum --dir data/curriculum/pdfs/
```

---

## Acceptance Criteria

- [ ] Script creates school, curricula adoption, trial subscription, and admin user in one run
- [ ] Re-running produces no duplicates and no errors (idempotent)
- [ ] School slug is auto-derived from name (lowercase, hyphens for spaces)
- [ ] Trial subscription has correct 15-day expiry from run date
- [ ] Temporary password printed to console only — not stored in any file or DB in plaintext
- [ ] Script works against both local Docker database and production Render database
- [ ] Integration test: run script against test DB → verify all 4 records created correctly
- [ ] Integration test: run script twice → second run produces zero new inserts, exits cleanly
- [ ] `seed_all_production.py` prints the correct ordered sequence with instructions

---

## Output From This Task

- Pilot school record in production database
- School Admin user with known temporary credentials
- Trial subscription active
- Cambridge curriculum adopted by the school
- Operator can hand credentials to the school's admin contact and pilot begins
