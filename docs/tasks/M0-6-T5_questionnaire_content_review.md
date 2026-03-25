# M0-6-T5 — Add SUBJECT_INTEREST_MAP to questionnaire_config.py
**Milestone:** M0 — Foundations
**Epic:** M0-6 — Student Onboarding Flow
**Task ID:** M0-6-T5
**Depends on:** M0-6-T1 (questionnaire_config.py exists with interest options already committed)
**Blocks:** M3-1-T2 (quiz generator must call get_compatible_interests before injecting interests into prompts)
**Estimated effort:** 1–2 hours
**Executor:** Coding agent

---

## Problem This Task Solves

`quiz_generator.py` (M3-1-T2) currently injects a student's top 2 interests directly
into the LLM prompt regardless of whether those interests are relevant to the subject
being quizzed.

**Example of the bug this creates:**

A student interested in `fashion` and `travel` takes a Physics quiz on Forces.
The prompt currently sends: *"Frame questions using the student's interests: fashion, travel."*
The LLM produces a forced scenario like: *"A fashion model walks down a runway at 2 m/s..."*
This is educationally damaging and reduces teacher trust in the platform.

**The fix:** Before injecting interests into the prompt, filter them through a
subject-specific compatibility map. If no compatible interests exist, skip
personalisation entirely — a plain quiz is always better than a forced one.

---

## Current interest options in questionnaire_config.py (DO NOT change these)

The following 10 options are already committed as part of M0-6-T1. This task does
not modify them:

```
sports, music, gaming, animals, cooking, art, technology, nature, fashion, travel
```

---

## SUBJECT_INTEREST_MAP — Decisions with Rationale

The table below defines which interests can be injected into each subject's quiz
prompts. The decision rule: an interest is compatible if the LLM can frame a
curriculum-accurate question scenario around it without the scenario feeling forced.

Each decision is documented here so that Vibhu can review and challenge it in the PR.

### MATH → `["sports", "music", "gaming", "cooking", "art", "technology"]`

| Interest | Cambridge curriculum connection |
|---|---|
| `sports` | Statistics (averages/range of match scores, league table data), probability (sports outcomes), ratio and proportion (distance/time/speed) |
| `music` | Fractions (time signatures — 3/4 beat = 3 quarter notes), sequences and series (musical patterns), ratio (tempo relationships) |
| `gaming` | Probability (dice outcomes, card game combinations), coordinate geometry (grid-based games), number sequences (level scoring systems) |
| `cooking` | Ratio and proportion (scaling recipes up/down), percentages (ingredient concentration), measurement and unit conversion (ml ↔ litres) |
| `art` | Geometry (symmetry, tessellation, transformations), scale and proportion (enlargements), pattern sequences |
| `technology` | Number sequences (algorithm steps), logic gates in IGCSE (Boolean expressions), number systems (binary/denary conversion) |

**Not included:** `animals`, `nature`, `travel`, `fashion` — the Cambridge Maths syllabus has no natural scenario hooks for these. Attempts produce nonsense (e.g. "A giraffe's neck is 1.8m — calculate the perimeter of the giraffe").

---

### SCI → `["animals", "cooking", "nature", "sports"]`
*(Cambridge Lower Secondary Integrated Science, Grades 6–8 only)*

| Interest | Cambridge curriculum connection |
|---|---|
| `animals` | Biology strand: classification, habitats, life processes, food webs, adaptation to environments |
| `cooking` | Chemistry strand: physical vs chemical changes (melting = physical, baking = chemical), states of matter, dissolving (solutions), acids (vinegar, baking powder) |
| `nature` | All three strands: ecosystems and food webs (bio), rock cycle and weathering (earth/chem), weather and climate (physics) |
| `sports` | Physics strand: forces (friction, gravity, air resistance), speed calculations, energy transfer in movement |

**Not included:** `music`, `gaming`, `art`, `technology`, `fashion`, `travel` — Cambridge Lower Secondary Science content does not have natural scenario hooks for these at Grades 6–8 level.

---

### ENG → `["travel", "music", "art", "nature"]`
*(English Language — both curricula)*

| Interest | Cambridge curriculum connection |
|---|---|
| `travel` | Descriptive writing (write about a place you have visited), reading comprehension passages (travelogues, travel articles), formal letter writing (hotel complaint) |
| `music` | Poetry analysis (rhythm, rhyme scheme, tone — concepts shared with music), persuasive writing (music review), identifying language techniques in song lyrics |
| `art` | Visual text analysis (reading posters, advertisements, magazine covers), descriptive writing (describe an artwork), media and multimodal texts |
| `nature` | Descriptive writing (nature imagery, seasons, weather as setting), reading comprehension passages (nature documentaries, environmental journalism) |

**Not included:** `sports`, `gaming`, `cooking`, `animals`, `technology`, `fashion` — while these could appear in English passages in principle, they do not map to the specific Cambridge English Language task types: descriptive, analytical, persuasive writing and structured reading comprehension.

---

### BIO → `["animals", "nature", "cooking", "sports"]`
*(Cambridge IGCSE Biology, Grades 9–10 only)*

| Interest | Cambridge curriculum connection |
|---|---|
| `animals` | Core IGCSE content: animal classification (kingdom to species), animal physiology (digestion, circulation, nervous system), genetics and variation, ecology (predator/prey) |
| `nature` | Ecology and ecosystems, plant biology (photosynthesis, transpiration), environmental science, biodiversity and conservation |
| `cooking` | Nutrition and food tests (Benedict's reagent for sugar, iodine for starch, biuret for protein), enzymes in digestion (temperature and pH effects), food preservation (bacteria, decomposition) |
| `sports` | Human physiology in context: muscles and movement (tendons, ligaments, antagonistic pairs), aerobic vs anaerobic respiration in exercise, nervous system and coordination |

**Not included:** `music`, `gaming`, `art`, `technology`, `fashion`, `travel` — IGCSE Biology content is specific enough that these produce forced, implausible scenarios.

---

### CHEM → `["cooking", "nature", "technology"]`
*(Cambridge IGCSE Chemistry, Grades 9–10 only)*

| Interest | Cambridge curriculum connection |
|---|---|
| `cooking` | Physical and chemical changes (baking bread = chemical, melting butter = physical), acids and alkalis (vinegar is ethanoic acid, baking powder releases CO₂), organic chemistry (food molecules — ethanol, esters), rate of reaction (yeast in bread rising) |
| `nature` | Environmental chemistry: air pollution (oxides of nitrogen and sulfur from combustion), acid rain and its effects, water purification (filtration, chlorination), carbon cycle and greenhouse gases, rusting as oxidation |
| `technology` | Industrial processes: Haber process (ammonia synthesis for fertilisers), Contact process (sulfuric acid manufacture), electrolysis (copper refining, aluminium extraction, electroplating), materials science (polymers, smart materials) |

**Not included:** `sports`, `music`, `gaming`, `animals`, `art`, `fashion`, `travel` — IGCSE Chemistry is abstract/molecular enough that these produce implausible scenarios. Chemistry already has credible real-world contexts (industrial, environmental) that are far more natural than forced interest hooks.

---

### PHY → `["sports", "music", "gaming", "technology"]`
*(Cambridge IGCSE Physics, Grades 9–10 only)*

| Interest | Cambridge curriculum connection |
|---|---|
| `sports` | Forces and motion (projectile motion, friction, collision momentum), energy (kinetic and potential energy in sport, efficiency), pressure (tyre pressure, footballer's studs on pitch), power (watt output of an athlete) |
| `music` | Sound waves (frequency, amplitude, wavelength, speed of sound), resonance and standing waves, decibel scale, echo and ultrasound |
| `gaming` | Digital electronics (logic gates — AND/OR/NOT, semiconductors), optics (how screens produce colour, pixel resolution, lenses in VR headsets), electromagnetic spectrum (WiFi, Bluetooth) |
| `technology` | Electricity and magnetism (motors, generators, transformers), nuclear physics (fission in power stations, half-life in carbon dating), space physics (satellite orbits, gravitational field strength) |

**Not included:** `animals`, `cooking`, `art`, `nature`, `fashion`, `travel` — while a physics principle could be forced into these contexts, it requires contrivance that reduces question quality and confuses the physics concept.

---

### ENGL → `["travel", "music", "art"]`
*(Cambridge IGCSE English Literature, Grades 9–10 only)*

| Interest | Cambridge curriculum connection |
|---|---|
| `travel` | Setting and cultural context in world literature set texts, journey as metaphor (self-discovery archetype appears across IGCSE poetry and prose anthologies), comparative essay contexts |
| `music` | Poetry analysis (rhythm, meter, tone, mood — musical concepts that scaffold literary analysis), comparing song lyrics to poems as a teaching scaffold, identifying onomatopoeia and sound imagery in verse |
| `art` | Ekphrasis (poems written about artworks — common in Cambridge Literature anthologies), visual imagery and colour symbolism in poetry, descriptive language in prose passages |

**Not included:** `sports`, `gaming`, `cooking`, `animals`, `nature`, `technology`, `fashion` — IGCSE English Literature is text-analysis focused. These interests would distort the analytical task rather than scaffold it.

---

### Why `fashion` appears in NO subject

`fashion` is intentionally absent from every subject in the map.

- No Cambridge subject at Grades 6–10 has natural curriculum hooks for fashion scenarios
- Injecting `fashion` into any quiz produces forced, awkward questions that undermine credibility
- A student who selects `fashion` simply receives unpersonalised quizzes — identical to a student who selects no interests at all
- This is **correct behaviour**, not a bug. Do NOT add `fashion` to any subject map.

---

## Implementation

### Step 1 — Add to `backend/app/core/questionnaire_config.py`

Add the following block **after** the closing `}` of `QUESTIONNAIRE_V1` and **before**
the `get_questionnaire_definition()` function. Do not change anything else in the file.

```python
# Subject-to-interest compatibility mapping.
#
# Purpose: prevents injecting irrelevant student interests into quiz generation prompts.
# quiz_generator.py calls get_compatible_interests() before building the LLM prompt.
# Only interests that fit the subject's Cambridge curriculum content are passed through.
#
# If a student's interests produce an empty list for the current subject, the quiz
# is generated without personalisation. A plain quiz is always better than a
# forced scenario that damages question quality.
#
# Decision rationale: docs/tasks/M0/M0-6-T5_questionnaire_content_review.md
# Vidhya review: docs/design/QUESTIONNAIRE_DESIGN_RATIONALE.md
SUBJECT_INTEREST_MAP: dict[str, list[str]] = {
    "MATH": ["sports", "music", "gaming", "cooking", "art", "technology"],
    "SCI":  ["animals", "cooking", "nature", "sports"],
    "ENG":  ["travel", "music", "art", "nature"],
    "BIO":  ["animals", "nature", "cooking", "sports"],
    "CHEM": ["cooking", "nature", "technology"],
    "PHY":  ["sports", "music", "gaming", "technology"],
    "ENGL": ["travel", "music", "art"],
    # Note: 'fashion' is absent from all subjects intentionally.
    # Students who select it receive unpersonalised quizzes — not a bug.
}


def get_compatible_interests(
    subject_code: str,
    student_interests: list[str],
) -> list[str]:
    """Return the student's interests that are compatible with the given subject.

    Called by quiz_generator.py before building the personalisation prompt section.
    Returns an empty list if no compatible interests exist — the caller then skips
    personalisation entirely rather than injecting a mismatched interest.

    Args:
        subject_code: Cambridge subject code e.g. "MATH", "BIO", "PHY".
                      Case-insensitive — "math" and "MATH" produce the same result.
        student_interests: List of interest keys from student_learning_profiles.interests.
                           Preserves the student's original preference order.

    Returns:
        Filtered list of interest keys compatible with this subject.
        Empty list if none match or if subject_code is unknown.

    Example:
        student has interests = ["fashion", "sports", "music"]

        get_compatible_interests("PHY", ["fashion", "sports", "music"])
        → ["sports", "music"]   # fashion excluded; sports + music in PHY map

        get_compatible_interests("PHY", ["fashion"])
        → []   # no compatible interests → caller skips personalisation
    """
    compatible = SUBJECT_INTEREST_MAP.get(subject_code.upper(), [])
    return [interest for interest in student_interests if interest in compatible]
```

### Step 2 — Note for M3-1-T2 implementer

When implementing `quiz_generator.py` in M3-1-T2, use this pattern:

```python
from app.core.questionnaire_config import get_compatible_interests

# CORRECT — filter before injecting
top_2_interests = get_compatible_interests(
    subject_code=subtopic.subject_code,
    student_interests=profile.interests or [],
)[:2]

# WRONG — never do this
top_2_interests = (profile.interests or [])[:2]
```

The Jinja2 template's `{% if top_2_interests %}` block handles the empty list case
automatically — no template changes needed.

**Do not modify M3-1-T2 task file.** Simply implement it correctly when the time comes.

---

## Files to Modify

```
backend/app/core/questionnaire_config.py        ← add SUBJECT_INTEREST_MAP + get_compatible_interests()
backend/tests/unit/test_questionnaire_config.py ← add new test classes below
```

No other files. Do not touch questionnaire questions, options, API routes, or schemas.

---

## Unit Tests

Add to `backend/tests/unit/test_questionnaire_config.py`:

```python
from app.core.questionnaire_config import (
    SUBJECT_INTEREST_MAP,
    get_compatible_interests,
)

KNOWN_INTEREST_KEYS = {
    "sports", "music", "gaming", "animals", "cooking",
    "art", "technology", "nature", "fashion", "travel",
}

EXPECTED_SUBJECT_CODES = {"MATH", "SCI", "ENG", "BIO", "CHEM", "PHY", "ENGL"}


class TestSubjectInterestMap:
    def test_map_contains_exactly_seven_cambridge_subject_codes(self) -> None:
        assert set(SUBJECT_INTEREST_MAP.keys()) == EXPECTED_SUBJECT_CODES

    def test_all_interest_values_are_known_option_keys(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            unknown = set(interests) - KNOWN_INTEREST_KEYS
            assert unknown == set(), (
                f"{subject} contains unknown interest keys: {unknown}"
            )

    def test_fashion_not_in_any_subject(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            assert "fashion" not in interests, (
                f"'fashion' must not appear in {subject} — see M0-6-T5 rationale"
            )

    def test_each_subject_has_at_least_two_interests(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            assert len(interests) >= 2, (
                f"{subject} has only {len(interests)} compatible interest(s) — "
                f"minimum 2 required for personalisation to be meaningful"
            )


class TestGetCompatibleInterests:
    def test_returns_matching_interests_preserving_student_order(self) -> None:
        result = get_compatible_interests("PHY", ["sports", "fashion", "music"])
        assert result == ["sports", "music"]  # fashion excluded, order preserved

    def test_returns_empty_when_no_interests_compatible(self) -> None:
        result = get_compatible_interests("MATH", ["fashion"])
        assert result == []

    def test_returns_empty_when_student_has_no_interests(self) -> None:
        assert get_compatible_interests("BIO", []) == []

    def test_returns_empty_for_unknown_subject_code(self) -> None:
        assert get_compatible_interests("UNKNOWN", ["sports", "music"]) == []

    def test_case_insensitive_subject_code(self) -> None:
        assert get_compatible_interests("math", ["sports"]) == \
               get_compatible_interests("MATH", ["sports"])

    def test_returns_all_matching_uncapped(self) -> None:
        # get_compatible_interests does not cap — caller does [:2]
        all_math = ["sports", "music", "gaming", "cooking", "art", "technology"]
        result = get_compatible_interests("MATH", all_math)
        assert len(result) == 6

    def test_caller_slice_pattern(self) -> None:
        # Confirm the top-2 pattern used in quiz_generator.py works correctly
        result = get_compatible_interests("PHY", ["sports", "music", "gaming", "technology"])
        assert result[:2] == ["sports", "music"]

    def test_sci_map(self) -> None:
        assert get_compatible_interests("SCI", ["animals", "fashion", "cooking"]) == [
            "animals", "cooking",
        ]

    def test_engl_map_smallest_set(self) -> None:
        # ENGL has only 3 compatible interests
        assert get_compatible_interests("ENGL", ["sports", "travel", "gaming", "art"]) == [
            "travel", "art",
        ]

    def test_chem_map(self) -> None:
        assert get_compatible_interests("CHEM", ["sports", "cooking", "nature", "gaming"]) == [
            "cooking", "nature",
        ]
```

---

## Acceptance Criteria

- [ ] `SUBJECT_INTEREST_MAP` constant added to `questionnaire_config.py` with all 7 subject codes
- [ ] `get_compatible_interests()` function added immediately below the constant
- [ ] Docstring includes a worked example showing fashion being excluded from PHY
- [ ] Comment in the map explains why `fashion` is absent from all subjects
- [ ] All unit tests pass: `pytest backend/tests/unit/test_questionnaire_config.py -v`
- [ ] `mypy backend/app/core/questionnaire_config.py` passes with zero errors
- [ ] No changes to `QUESTIONNAIRE_V1`, any question text, or any API route

---

## Do NOT Touch

- `QUESTIONNAIRE_V1` — questions, options, `maps_to` mappings are frozen
- `questionnaire_version = "v1"` — bumping is a future decision
- `onboarding_service.py` — reads interests as-is, no change needed
- Any existing tests in `test_questionnaire_config.py` — only add new classes
- Any API routes, schemas, or migration files
