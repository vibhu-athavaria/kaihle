# ADR-002 — IB Curriculum Roadmap
**Date:** March 2026
**Status:** Accepted
**Authors:** Vidhya (curriculum strategy) + Kramer (technical constraints)
**Supersedes:** Nothing
**Referenced in:** CONSTITUTION.md §1 (curriculum scope), kaihle_product_plan.md

---

## Context

Kaihle v1 ships with Cambridge Lower Secondary and Cambridge IGCSE curricula only.
The product plan has always mentioned IB (International Baccalaureate) as the next
curriculum to add. This ADR documents:
1. Which IB programme ships first and why
2. The grade range and subject scope for v1 IB support
3. The technical constraints that affect IB implementation
4. The timeline relative to the Cambridge pilot

This document exists because technical decisions made in v1 (schema design, data
structures, API contracts) will directly affect how easy or hard IB is to add later.
Without this ADR, the team may make v1 technical decisions that create unnecessary
IB migration debt.

---

## Decision

### Which IB programme ships first: MYP

**Middle Years Programme (MYP)** for Grades 6–10 ships as the second curriculum, after
the Cambridge pilot has demonstrated product-market fit (estimated 3–6 months post-launch).

**Rationale for MYP over DP:**
- MYP grade range (6–10) exactly matches the current Cambridge scope (Lower Secondary
  + IGCSE). Same student cohort. Same teacher audience. Zero schema changes needed.
- MYP is used by most of the same international schools that use Cambridge — the likely
  first expansion schools are already familiar with both frameworks.
- DP (Diploma Programme, Grades 11–12) requires a significant schema extension (internal
  assessments, predicted grades, Theory of Knowledge component) and is explicitly out of
  scope for v1.

### IB MYP subject mapping

| IB MYP Subject Group | Cambridge equivalent | Kaihle v1 handling |
|---|---|---|
| Language & Literature | English Language (ENG) | Map to ENG subject code |
| Language Acquisition | Not in Cambridge scope | New subject code: `LANG` |
| Individuals & Societies | Not in Cambridge scope | New subject code: `HUMSS` |
| Sciences | Biology/Chemistry/Physics (separate) | Split into BIO/CHEM/PHY |
| Mathematics | Mathematics (MATH) | Map to MATH subject code |
| Arts | Not in Cambridge scope | New subject code: `ARTS` |
| PHE (Physical & Health) | Not in Cambridge scope | Out of scope for v2 |
| Design | Not in Cambridge scope | New subject code: `DESIGN` |

**v2 impact:** 4 new subject codes needed (`LANG`, `HUMSS`, `ARTS`, `DESIGN`). The
`subjects` table supports this without schema changes — just new rows.

### IB MYP vs Cambridge key differences requiring technical work

| Dimension | Cambridge | IB MYP | Technical impact |
|---|---|---|---|
| Assessment model | Primarily MCQ + short answer | Criterion-based (A-D rubrics) | Medium — new question types |
| Learning objectives | Per-subtopic, text | MYP "Key Concepts" + "Related Concepts" | Medium — new fields in curriculum schema |
| Global contexts | Not applicable | Required by IB | Low — metadata field on lesson plans |
| ATL skills | Not applicable | Approaches to Learning | Low — metadata |
| Personal Project | Gr.10 capstone | Required by IB | High — entirely new feature |
| eAssessment | Not applicable | Optional in IB | Out of scope |

**Assessment model difference is the most significant:**
IB MYP does not primarily use MCQ. It uses open-ended criterion-based tasks assessed
against 4 criteria (A: Knowing, B: Investigating, C: Communicating, D: Reflecting) each
scored 0–8. This means:
1. The question bank is not reusable for MYP-specific assessments
2. The `scoring` system (currently deterministic MCQ) would need a new scoring pathway
3. For v2, limit MYP support to **diagnostic MCQ only** (same as Cambridge) and defer
   authentic MYP criterion-based assessment to v3

### Timeline

| Milestone | Estimated date |
|---|---|
| Cambridge pilot live | Post-M6 (v1) |
| Pilot feedback (1–3 months) | 3–4 months post-launch |
| IB MYP v2 scoping sprint | Month 4–5 post-launch |
| IB MYP data authoring (Vidhya) | Month 5–6 |
| IB MYP v2 development | Month 6–9 |
| IB MYP pilot | Month 9–12 |

---

## v1 Technical Constraints to Preserve for IB

### 1. Never hardcode curriculum codes in route logic

All routes use `curriculum_id` as a UUID parameter. No route should contain `if curriculum_code == "cambridge_lower"`. This is already enforced by the schema design — curriculum is a FK, not a string check.

### 2. The `curriculum_subjects` join table is the right abstraction

Subject-to-curriculum binding via the `curriculum_subjects` join table is the correct
design. Adding MYP subjects means adding rows to `curriculum_subjects`, not altering
the schema.

### 3. `subject_code` must not embed curriculum knowledge

Subject codes (`MATH`, `BIO`, etc.) are curriculum-agnostic in the design. Both
Cambridge IGCSE Mathematics and IB MYP Mathematics use `MATH`. This is correct.

### 4. The `learning_objective` field is free text — keep it that way

IB uses "Key Concepts" and "Related Concepts" as structured objects. Rather than
adding new columns to `subtopics` now (which would be unused for Cambridge), the IB
metadata will be stored in a new `subtopic_ib_metadata` JSON field added in v2.
Do not add this field to the v1 schema.

### 5. The lesson plan prompt uses `curriculum_code` — keep it parameterised

The `lesson_plan_user.jinja2` template takes `curriculum_code` as a variable. When
IB is added, passing `curriculum_code="ib_myp"` will allow a different prompt template
to be selected. This is already the correct design.

---

## Rejected alternatives

### Alternative: Ship DP (Grades 11–12) first
Rejected. DP has entirely different assessment mechanics (IAs, extended essays, predicted
grades). Too high a complexity delta from v1. MYP is the right stepping stone.

### Alternative: Build IB support in v1
Rejected. No IB schools in the pilot school target list. Adding IB in v1 would delay
the Cambridge pilot by 2–3 months. The correct approach is ship → learn → expand.

### Alternative: Common Core as second curriculum
Rejected for v2. Common Core targets US/international American schools. Bali has limited
American-curriculum schools. MYP is more relevant to the target market (international
schools globally). Common Core is v3 or later.

---

## Consequences

**Positive:**
- v1 ships cleanly without IB complexity
- Schema design supports IB without changes
- Team has clear roadmap for v2 scope

**Negative (accepted):**
- MYP criterion-based assessment is deferred — MYP schools using Kaihle v2 will only
  get diagnostic MCQ, not authentic MYP-style assessments
- `LANG`, `HUMSS`, `ARTS`, `DESIGN` subject codes are not in v1 — MYP schools cannot
  use those subjects until v2

**Required follow-up before v2:**
- Vidhya must author `ib_myp_v1.json` curriculum data (same format as `cambridge_v1.json`)
- A new `M1-2-T1`-equivalent task will seed this data
- A new `M1-2-T3`-equivalent curriculum review task applies before MYP data ships

---

*ADR-002 · IB Curriculum Roadmap · Vidhya (curriculum strategy) + Kramer (technical) · March 2026*
