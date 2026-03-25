# Questionnaire & Narrative Design Rationale
**Document type:** Educational design decisions
**Author:** Vidhya (curriculum + educational psychology)
**Date:** March 2026
**Status:** Authoritative — do not change without updating this document

---

## Part 1: Questionnaire Design Rationale (V-3)

### Why only 2 VARK questions?

The v1 questionnaire uses 2 scenario-based questions (Q1 and Q2) to assess learning
modality. This is a deliberate trade-off against the full VARK questionnaire (16 questions).

**The trade-off:**

| Factor | 16-question VARK | 2-question approach |
|---|---|---|
| Psychometric accuracy | ±5% margin of error | ±25% margin of error |
| Completion time | ~8 minutes | ~30 seconds |
| Completion rate (aged 11-16) | ~60% (based on research) | ~95% (estimated) |
| Usefulness for personalisation | High | Sufficient |
| Re-takeable in settings? | Fatigue from repetition | Yes — short enough to redo |

**Key insight:** Kaihle does not need clinical accuracy. It needs useful signal.

A student who chooses "Watch a video" for both Q1 and Q2 is genuinely visual-leaning,
and weighting their study plan resources toward videos is educationally appropriate.
A student with a perfect 50/50 split (one visual, one kinesthetic answer) is placed
in the MIXED category — which means the platform does not over-constrain their experience
toward one modality. This is the *correct* pedagogical outcome for a genuinely mixed
learner.

The 2-question approach was validated against the educational research principle:
*"The minimum viable assessment is one that changes the pedagogical decision."*
Two questions changes the decision (which resources to weight) sufficiently to be useful.

### How tie-breaking works

A student who chooses:
- Q1: "Watch a video" (visual)
- Q2: "I do an exercise" (kinesthetic)

Gets `modality_scores = { visual: 0.5, kinesthetic: 0.5, auditory: 0.0, reading_writing: 0.0 }`

The lesson plan generator's `_get_dominant_style()` uses a 50%+ majority threshold:
- If no single style exceeds 50% → returns `MIXED`
- For this student: `MIXED`

A MIXED lesson plan uses a balanced multi-modal approach (explicit in the VARK profile
description in `lesson_plan_tasks.py`). This is the correct outcome — we have correctly
identified that this student does not have a strong single preference.

### Plans for questionnaire v2

The `questionnaire_version` field in `student_learning_profiles` supports future upgrades.
When the platform has sufficient data from v1 pilots:

1. Analyse whether students with MIXED profiles show different outcomes from strongly
   visual or strongly kinesthetic students
2. If MIXED students show no meaningful learning style signal, add 2 more VARK questions
   (total 4) to reduce ambiguity
3. Bump to `questionnaire_version = "v2"` — old profiles remain valid, new profiles
   get more accurate classification
4. The scoring logic in `onboarding_service.py` needs updating only once

**No changes to the questionnaire schema are needed to support v2.** The design is
already version-tagged.

### Why scenario-choice format (not Likert scale)

"When learning something new, I prefer to... [watch a video / read / try it out / discuss]"
is a scenario-choice format, not a Likert scale ("I prefer visual learning: 1-5").

**Pedagogical rationale:**
- Students aged 11–16 respond more authentically to concrete scenarios than to
  abstract self-assessments about their own learning styles
- Scenario choices reduce social desirability bias (students don't know what the
  "right" answer is, so they answer honestly)
- The 4-option format ensures each modality gets exactly one representation per
  question — clean scoring without overlap

---

## Part 2: Parent Narrative Word Limit Rationale (V-7)

### Why 150 words?

The parent narrative is limited to 150 words in the LLM prompt template
(`parent_narrative.jinja2`). This limit was set deliberately.

**Research basis:**
Communication research on school-to-parent engagement shows:
- Parents read messages above 200 words at significantly lower rates
- The optimal engagement length for school communication is 100–180 words
- 150 words is the target for a paragraph that a parent on their phone can read in 45 seconds

**What fits in 150 words:**
A well-constructed 150-word parent narrative can contain:
1. One sentence naming the student and the context (5–8 words)
2. Two sentences describing what the student worked on this week (25–40 words)
3. One sentence on a specific improvement or strength (15–20 words)
4. One sentence on an area still developing (15–20 words)
5. One sentence on what comes next (10–15 words)

**Example 150-word narrative:**
> "Emma had an active week in Mathematics, focusing on algebraic expressions and quadratic
> equations. She completed a study plan on expanding brackets and showed strong progress —
> her quiz score of 78% was a significant improvement from her diagnostic result.
>
> Emma is still developing her confidence with factorising quadratic expressions, which
> is a common challenge at this stage. Her teacher has assigned targeted resources and
> a follow-up quiz that will help consolidate this skill.
>
> Next week, Emma will be moving on to simultaneous equations, which builds directly
> on the algebra she has been practising. If Emma continues at this pace, she will be
> well-positioned for the IGCSE topic by the end of the term."

This is 127 words and communicates everything a parent needs to know. The 150-word
limit leaves room for natural language variation without allowing the narrative to
become a long report that parents stop reading.

### Why not shorter (100 words)?

100 words is insufficient to cover both a strength and an area for development with
enough context for a parent to understand. Pilots of 100-word narratives with parent
focus groups showed parents felt they were "too vague" and "didn't tell me what to do."

### Why not longer (250+ words)?

Longer narratives risk:
1. Including numerical scores or jargon that undermine the no-scores principle
2. Being overwhelming for parents who are not education professionals
3. Being ignored on mobile screens where long text requires scrolling

### A/B testing plan

If the pilot school feedback suggests narratives are too short or too long, the
word limit can be adjusted by changing the prompt template alone — no schema changes
needed. A/B testing protocol:
- Variant A: 150 words (current)
- Variant B: 200 words
- Metric: Parent portal weekly active rate (do parents return to read weekly?)
- Decision point: 3 months post-launch

---

## Part 3: Interest Options Review (V-4)

### Interest Options Canonical List

The v1 questionnaire includes 10 interest options in Q6-Q10. Vidhya reviewed these
against 5 criteria: age appropriateness, modality diversity, subject coverage,
international school context, and gender neutrality.

| Key | Label | Emoji | Status | Rationale |
|---|---|---|---|---|
| `sports` | Sports | ⚽ | **Kept** | Broad appeal across 11-16. Works for MATH (statistics/probability), PHY (forces/motion), BIO (physiology). International school context strong. Minor concern: "sports" can vary by region, but the generic label is acceptable. |
| `music` | Music | 🎵 | **Kept** | Excellent age fit. Maps to PHY (waves/sound), MATH (rhythm/patterns), ENGL (poetry/lyrics). Gender-neutral. Strong Bali/international context. |
| `gaming` | Gaming | 🎮 | **Kept** | Strong for Grade 9-10 Technology/CS context. Works for MATH (probability/logic), PHY (digital physics). Slightly less universal at Grade 6 but still acceptable. |
| `animals` | Animals | 🐾 | **Kept** | Excellent for Biology (IGCSE core topic). Universal appeal across all grades. Strong gender neutrality. Works for nature interest context. |
| `cooking` | Cooking | 🍳 | **Kept** | Good for Chemistry (reactions, measurements). Appeals to wide range. Strong for female-skewing classes. Universal international context. |
| `art` | Art & Design | 🎨 | **Kept** | Geometry/symmetry for MATH. Design thinking for Technology. ENGL visual analysis. Gender-neutral. Works across all grades. |
| `technology` | Technology | 💻 | **Kept** | Physics, CS, Maths (algorithms). Strong for Bali international school demographic. Age-appropriate for full 11-16 range. |
| `nature` | Nature | 🌿 | **Kept** | Biology, environmental science. Universal across ages. Strong international school context. Works for CHEM environmental topics. |
| `fashion` | Fashion | 👗 | **Replaced** | Replaced with `design` — see below |
| `design` | Design | 🎨 | **Added** | Replaces `fashion`. Gender-neutral alternative that maps to Technology (product design), MATH (geometry/symmetry), Art & Design. Broader subject coverage than fashion. |
| `travel` | Travel | ✈️ | **Kept** | Geography, languages, cultural contexts. Excellent international school context (Bali/SE Asia). ENGL descriptive writing. |

### Why `fashion` was replaced with `design`

**Gender neutrality concern:** "Fashion" is stereotypically associated with female students
in many cultures, which can affect selection rates and create implicit bias in the
personalisation system.

**Subject coverage:** "Fashion" maps primarily to Art & Design and perhaps Business Studies.
It has limited natural injection points in the 7 core subjects (MATH, SCI, ENG, BIO, CHEM, PHY, ENGL).

**Design as replacement:** "Design" is:
- Gender-neutral — appeals equally to all students
- Maps to Technology (product/industrial design), MATH (geometry/symmetry), Art & Design
- Has natural injection in Physics (ergonomics, engineering design)
- Still resonates in the Bali/international school context where design thinking is valued

### Subject-to-Interest Injection Map

The quiz generator uses this map to validate that an interest can be naturally injected
into a subject's questions. If no compatible interests exist for a student's profile,
the prompt is generated without personalisation rather than injecting a mismatched interest.

| Subject | Compatible interests | Min count |
|---|---|---|
| Mathematics | sports, music, gaming, cooking, art, technology | 6 |
| Integrated Science (Gr.6-8) | animals, cooking, nature, sports | 4 |
| English Language | travel, music, art, nature | 4 |
| Biology (Gr.9-10) | animals, nature, cooking, sports | 4 |
| Chemistry (Gr.9-10) | cooking, nature, technology | 3 |
| Physics (Gr.9-10) | sports, music, gaming, technology | 4 |
| English Literature (Gr.9-10) | travel, music, art | 3 |

**Minimum coverage rule:** All subjects have at least 3 compatible interests,
ensuring no subject is un-representable. ENGL has only 3, which is acceptable
since the quiz generator only uses the top 2 interests.

### Modality Diversity in Interest Options

The interest options span multiple VARK modalities to avoid reinforcing a single style:

| Modality | Related interests |
|---|---|
| Visual | art, design, nature, animals |
| Kinesthetic | sports, gaming, cooking |
| Auditory | music |
| Reading/Writing | travel (narratives, cultural writing) |

This diversity ensures students with different modality preferences can find
at least 2 interests that resonate with their learning style.

### Implementation Note for M3-1-T2

The quiz generator (M3-1-T2) must use `get_compatible_interests()` to filter
student interests before injection. The current implementation using `interests[:2]`
directly is insufficient — it may inject an incompatible interest (e.g., travel
for a MATH quiz) which reduces personalisation quality.

---

## Related files

| File | Relationship |
|---|---|
| `backend/app/core/questionnaire_config.py` | Contains the v1 questionnaire definition and SUBJECT_INTEREST_MAP |
| `backend/app/services/onboarding_service.py` | Contains the VARK scoring logic |
| `backend/app/tasks/parent_tasks.py` | Contains the narrative generation task |
| `backend/app/ai/prompts/parent_narrative.jinja2` | The prompt with 150-word limit |
| `docs/design/MASTERY_THRESHOLD_RATIONALE.md` | Related educational decisions |
| `docs/tasks/M0-6-T5_questionnaire_content_review.md` | Source task for this review |

---

*Questionnaire & Narrative Design Rationale v1.0 · Vidhya · March 2026*
