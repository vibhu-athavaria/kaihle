# M0-6-T5 — Questionnaire Content Review & VARK Rationale
**Milestone:** M0 — Foundations
**Epic:** M0-6 — Student Onboarding Flow
**Task ID:** M0-6-T5
**Depends on:** M0-6-T1 (questionnaire API + questionnaire_config.py must exist)
**Blocks:** M1-2-T1 (curriculum seeding — quiz personalisation is meaningless without reviewed interests), M3-1-T2 (quiz generator uses interests directly)
**Estimated effort:** 3–4 hours
**Lead persona:** Vidhya (curriculum + educational psychology) with Kramer (implementation)

> **Why this task exists:**
> The `questionnaire_config.py` file contains 10 interest options and a 2-question VARK
> approach that were implemented without a formal educational review or documented rationale.
> These choices directly affect how quiz questions are personalised for 11–16 year old
> students at international schools. Before M1 ships — and before ANY student completes
> the questionnaire — Vidhya must review, confirm, and document these decisions.
> Undocumented educational choices become unexplainable product decisions when teachers ask.

---

## Vidhya — Educational Review Scope

### Part 1: Interest Options Review

The current 10 interest options in `questionnaire_config.py` are:

| Key | Label | Emoji | Review Question |
|---|---|---|---|
| `sports` | Sports | ⚽ | Too broad — "sports" injects "football/basketball/etc." depending on LLM. Should be specific? |
| `music` | Music | 🎵 | ✓ Works globally for 11–16. Maps well to Physics (waves/sound), Maths (rhythm/patterns) |
| `gaming` | Gaming | 🎮 | ✓ Strong for Technology/CS context. Works for Grade 9-10 well. Slightly less Gr.6 |
| `animals` | Animals | 🐾 | ✓ Excellent for Biology (IGCSE). Works across all grades. |
| `cooking` | Cooking | 🍳 | ✓ Chemistry (reactions, measurements). Good for female-skewing classes. |
| `art` | Art & Design | 🎨 | ✓ Geometry (patterns, symmetry). Design thinking for Technology. |
| `technology` | Technology | 💻 | ✓ Physics, CS, Maths. Strong for Bali international school demographic. |
| `nature` | Nature | 🌿 | ✓ Biology, environmental science. Works across all ages. |
| `fashion` | Fashion | 👗 | ? May feel gender-stereotyped. Consider replacing with "design" or "culture" |
| `travel` | Travel | ✈️ | ✓ Geography, languages, cultural contexts. Good for international school context. |

**Vidhya's review criteria:**
1. **Age appropriateness** — do all 10 work for 11–16 year olds without being condescending or irrelevant?
2. **Modality diversity** — do the options span visual (art, nature), kinesthetic (sports, cooking), reading/writing (travel narratives), and auditory (music) domains to avoid reinforcing a single modality?
3. **Subject coverage** — can each interest be naturally injected into at least 2 of the 7 subjects (MATH, SCI, ENG, BIO, CHEM, PHY, ENGL)?
4. **International school context** — do these resonate in a Bali/Southeast Asia international school setting?
5. **Gender neutrality** — are any options stereotyped by gender in a way that affects which students select them?

**Vidhya's deliverable:**
A confirmed canonical list (may be unchanged, modified, or partially replaced) with:
- Rationale for each kept option
- Replacement suggestions for any removed options
- A subject-to-interest injection mapping table (see below)

**Subject-to-interest injection mapping (to be completed by Vidhya):**

This table guides the quiz generator prompt. The LLM is told: "frame questions in the context of {interest} where it fits naturally." The mapping below ensures at least 2 interests per subject exist — if fewer than 2, a subject cannot be adequately personalised.

| Subject | Compatible interests (suggested — Vidhya to confirm) |
|---|---|
| Mathematics | sports (statistics/probability), music (rhythm patterns), gaming (probability/logic), cooking (measurement/ratios), art (geometry/symmetry), technology (algorithms) |
| Integrated Science (Gr.6-8) | animals (biology strand), cooking (chemistry strand), nature (all strands), sports (forces/motion strand) |
| English Language | travel (descriptive writing), music (poetry/rhythm), art (visual analysis), nature (descriptive writing) |
| Biology (Gr.9-10) | animals (core topic), nature (core topic), cooking (nutrition/enzymes), sports (physiology) |
| Chemistry (Gr.9-10) | cooking (reactions/organic), nature (environmental chem), technology (industrial processes) |
| Physics (Gr.9-10) | sports (forces/momentum), music (waves/sound), gaming (digital physics), technology (electricity) |
| English Literature (Gr.9-10) | travel (setting/context), music (analysis of song lyrics as text), art (visual poetry connections) |

---

### Part 2: VARK Scoring Rationale

**Current implementation:** 2 questions (Q1, Q2) determine VARK modality scores.

**The design question:** Real VARK questionnaires use 16 questions per modality. With only 2 questions and 4 modalities, each question maps to one modality choice. Result: many students will score exactly 0.5/0.5 on two modalities (tie) and 0.0 on the others.

**Vidhya's documented rationale for 2 questions:**

The 2-question approach is a deliberate trade-off:

| Factor | Detail |
|---|---|
| **Completion rate** | Research shows questionnaire abandonment increases sharply after 6 questions. 5-minute target requires limiting total questions to ≤10. With 3 work-style questions and 1 interest block, 2 VARK questions is the maximum budget. |
| **Age group** | Students aged 11–16 have lower patience for abstract psychometric instruments than adult learners. A 16-question VARK would see significant abandonment. |
| **Accuracy vs utility** | The goal is not clinical accuracy — it is useful signal. A 2-question instrument gives enough signal to weight resource curation and activity design. A student who chooses "watch a video" twice is genuinely more visual than one who chose "try it out hands-on" twice. |
| **Tie handling** | A tied student (e.g. 0.5 visual / 0.5 kinesthetic) generates a MIXED lesson plan group. This is educationally appropriate — not all students have a single dominant style. |
| **V2 plan** | Questionnaire v2 (post-pilot) will add 2 more VARK questions (Q2b, Q2c) based on pilot feedback. The `questionnaire_version` field in the schema supports this upgrade path. |

---

## Kramer — Implementation Deliverables

### Part 1: Update `questionnaire_config.py`

After Vidhya confirms the canonical interest list, apply any changes to:

```
backend/app/core/questionnaire_config.py
```

Specifically:
- Update the `options` list inside `q6_to_q10`
- If `fashion` is replaced, update the key, text, and emoji
- Do NOT change question IDs, question text, or any Q1–Q5 logic
- The `maps_to: "interests"` mapping does not change

### Part 2: Add Subject-Interest Injection Map

Add a new constant to `questionnaire_config.py`:

```python
# Subject-to-interest compatibility mapping.
# Used by quiz_generator.py to validate that a chosen interest is relevant
# before injecting it into the LLM prompt.
# If a student's top interests don't map to the current subject, the prompt
# is generated without personalisation rather than injecting a mismatched interest.
SUBJECT_INTEREST_MAP: dict[str, list[str]] = {
    "MATH": ["sports", "music", "gaming", "cooking", "art", "technology"],
    "SCI":  ["animals", "cooking", "nature", "sports"],
    "ENG":  ["travel", "music", "art", "nature"],
    "BIO":  ["animals", "nature", "cooking", "sports"],
    "CHEM": ["cooking", "nature", "technology"],
    "PHY":  ["sports", "music", "gaming", "technology"],
    "ENGL": ["travel", "music", "art"],
}

def get_compatible_interests(
    subject_code: str,
    student_interests: list[str],
) -> list[str]:
    """Return the student's interests that are compatible with the given subject.
    
    Called by quiz_generator.py before building the personalisation prompt section.
    Returns an empty list if no compatible interests exist — the caller then skips
    personalisation entirely rather than injecting an irrelevant interest.
    
    Args:
        subject_code: e.g. "MATH", "BIO", "PHY"
        student_interests: list of interest keys from the student's profile
    
    Returns:
        Filtered list of interest keys compatible with the subject.
    """
    compatible = SUBJECT_INTEREST_MAP.get(subject_code.upper(), [])
    return [i for i in student_interests if i in compatible]
```

### Part 3: Create Documentation

Create `docs/design/QUESTIONNAIRE_DESIGN_RATIONALE.md` (see separate doc task).

### Part 4: Update Quiz Generator

In `M3-1-T2_quiz_generator.md`, the quiz generator currently uses `student.interests[:2]`
directly. After this task, it must call `get_compatible_interests(subject_code, interests)`
instead, and only inject the result if it is non-empty:

```python
# In quiz_generator.py — update the prompt context building:
from app.core.questionnaire_config import get_compatible_interests

compatible = get_compatible_interests(
    subject_code=subtopic.subject_code,
    student_interests=profile.interests or [],
)
# compatible is [] if student has no relevant interests for this subject
# The Jinja2 template already handles empty list correctly:
# {% if top_2_interests %} ... {% endif %}
top_2_interests = compatible[:2]
```

This is a minor update to `M3-1-T2` — add it to that task file's "Do NOT Touch"
corrections section, noting this change is required before M3 begins.

---

## Files to Create / Modify

```
backend/app/core/questionnaire_config.py          ← MODIFY: update interests list + add SUBJECT_INTEREST_MAP
docs/design/QUESTIONNAIRE_DESIGN_RATIONALE.md      ← CREATE (Vidhya writes, Kramer formats)
docs/tasks/M3/M3-1-T2_quiz_generator.md           ← MODIFY: add note about get_compatible_interests
backend/app/tests/unit/test_questionnaire_config.py ← MODIFY: add tests for get_compatible_interests
```

---

## Unit Tests

Add to `test_questionnaire_config.py`:

```python
class TestGetCompatibleInterests:
    def test_get_compatible_when_student_has_relevant_interests_then_returns_them(self):
        result = get_compatible_interests("MATH", ["sports", "fashion", "gaming"])
        assert "sports" in result
        assert "gaming" in result
        assert "fashion" not in result  # fashion is not in MATH map

    def test_get_compatible_when_no_relevant_interests_then_returns_empty(self):
        result = get_compatible_interests("MATH", ["fashion", "travel"])
        # Neither fashion nor travel maps to MATH
        assert result == []

    def test_get_compatible_when_empty_interests_then_returns_empty(self):
        assert get_compatible_interests("BIO", []) == []

    def test_get_compatible_when_unknown_subject_then_returns_empty(self):
        # Unknown subject code should not crash — return empty list
        assert get_compatible_interests("UNKNOWN_SUBJECT", ["sports", "music"]) == []

    def test_get_compatible_is_case_insensitive_on_subject_code(self):
        # "math" and "MATH" should produce the same result
        assert get_compatible_interests("math", ["sports"]) == \
               get_compatible_interests("MATH", ["sports"])

    def test_get_compatible_returns_max_available_not_capped(self):
        # All 6 compatible interests for MATH
        all_math = ["sports", "music", "gaming", "cooking", "art", "technology"]
        result = get_compatible_interests("MATH", all_math)
        assert len(result) == 6  # function returns all, caller does [:2]
```

---

## Acceptance Criteria

- [ ] Vidhya has reviewed all 10 interest options against age range, modality diversity, subject coverage, and gender neutrality
- [ ] Each kept interest has a written rationale in `QUESTIONNAIRE_DESIGN_RATIONALE.md`
- [ ] Any replaced interest has a replacement rationale
- [ ] Subject-to-interest mapping table is complete and documented
- [ ] `SUBJECT_INTEREST_MAP` constant added to `questionnaire_config.py`
- [ ] `get_compatible_interests()` function added and tested
- [ ] VARK 2-question rationale is documented in `QUESTIONNAIRE_DESIGN_RATIONALE.md`
- [ ] Tie-handling (MIXED) is documented
- [ ] All unit tests pass
- [ ] `mypy app/` passes with zero errors

---

## Do NOT Touch

- Q1–Q5 questions or their `maps_to` mappings — these are frozen
- The questionnaire version tag (`"v1"`) — bumping to v2 is a future decision
- `onboarding_service.py` scoring logic — it reads interests as-is from the response
- Any existing integration tests for the questionnaire API
