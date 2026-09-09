# Draft — Teacher-Facing Changelog for the Mastery Score Update

**Status: DRAFT. Not sent. Vibhu reviews and sends when the rebuild is applied.**

---

**Subject: An update to how mastery scores are calculated**

Hi everyone,

We've improved how Kaihle calculates mastery scores, and you may notice some numbers have
changed for your students. Here's what happened and why.

**What changed.** The previous calculation applied a flat, one-size-fits-all discount to
every student's first assessment in a subject — regardless of how many questions they
answered or how well they did. This had an unintended side effect: a student who answered
every question correctly could never be shown as "Strong," because the discount capped
their score just below that threshold. Every top performer showed up as "Developing," no
matter how well they actually did.

The new calculation adjusts its confidence based on the actual amount of evidence behind
each score — a student who's answered a handful of questions is judged more cautiously
than one with a long track record, and that caution fades appropriately as more evidence
comes in. A student who aces their diagnostic can now correctly show as "Strong."

**What this means for you.** Some students' scores will move — mostly upward for strong
performers who were previously held back by the old cap, though some scores will also
shift down or up slightly as the new calculation weighs recent performance more
precisely. The color bands you're used to (green/amber/red) work exactly the same way;
what's changed is how accurately the number underneath reflects what a student has
actually shown.

**What stays the same.** Nothing about how you use the gap map changes. The bands, the
provisional (dashed-border) indicator for scores with limited evidence, and every other
part of the interface are unchanged.

If you notice a score that looks surprising, that's worth a second look together with us —
we'd rather hear about it than have it go unnoticed.

Thanks,
[Vibhu / Kaihle team]

---

*Internal note: send once `scripts/rebuild_mastery.py --apply` has run in prod and the
before/after numbers have been reviewed (see MASTERY_MODEL_RATIONALE.md's rollout
section). Adjust tone/specifics for the actual audience (a single pilot school vs.
several) before sending.*
