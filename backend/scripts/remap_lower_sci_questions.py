"""Remaps question_bank rows for cambridge_lower SCI from old discipline-split
subtopics (SCI-BIO, SCI-CHEM, SCI-PHY, SCI-EARTH) to the correct Cambridge 0893
integrated unit subtopics, then deletes the now-empty stale rows.

Run AFTER patch_curriculum_v3 — the new integrated subtopics must exist first.

Safe to run multiple times — fully idempotent:
  - If old subtopics have already been deleted, the remap step finds nothing to update.
  - If questions are already on new subtopics, the UPDATE touches zero rows.
  - DELETE steps are no-ops if rows are already gone.

Works with any DATABASE_URL: dev Docker (port 5433) or prod Render.com.

Usage (from project root):
    # With Docker running:
    docker compose exec backend python -m scripts.remap_lower_sci_questions

    # Dry run (shows what would happen — no DB writes):
    docker compose exec backend python -m scripts.remap_lower_sci_questions --dry-run

    # Outside Docker (requires DATABASE_URL in env):
    cd backend
    DATABASE_URL=postgresql+asyncpg://... python -m scripts.remap_lower_sci_questions

What this does (in a single transaction):
    1. Builds a mapping from old stale subtopic IDs to new correct subtopic IDs
    2. Updates question_bank.subtopic_id to point to new subtopics
    3. Verifies zero questions remain on old subtopics
    4. Deletes stale subtopic rows (SCI-BIO-G6-*, SCI-CHEM-G6-*, etc.)
    5. Deletes stale curriculum_topics rows (SCI-BIO, SCI-CHEM, SCI-PHY, SCI-EARTH
       for cambridge_lower / SCI)
    6. Verifies no orphan questions exist
    7. Commits (or rolls back on any error)
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Mapping: old canonical_code → new canonical_code
# Determined by content analysis — see docs/curriculum_research/ for rationale.
# ---------------------------------------------------------------------------
SUBTOPIC_REMAP: dict[str, str] = {
    # ── GRADE 6 ──────────────────────────────────────────────────────────────
    "SCI-BIO-G6-01": "SCI-CELLS-G6-01",  # Cells and Cell Functions → Cell Structure and Function
    "SCI-BIO-G6-02": "SCI-LIFE-G6-03",  # Photosynthesis → Ecosystems and Food Webs (G6 producer context)
    "SCI-BIO-G6-03": "SCI-LIFE-G6-03",  # Ecosystems and Food Chains → Ecosystems and Food Webs
    "SCI-BIO-G6-04": "SCI-LIFE-G6-01",  # Characteristics of Living Things → Characteristics of Living Organisms
    "SCI-BIO-G6-05": "SCI-LIFE-G6-02",  # Classification of Organisms → Classification and Dichotomous Keys
    "SCI-BIO-G6-06": "SCI-LIFE-G6-04",  # Habitats and Adaptation → Biodiversity and Adaptation
    "SCI-CHEM-G6-01": "SCI-MATTER-G6-03",  # States of Matter → States of Matter and the Particle Model
    "SCI-CHEM-G6-02": "SCI-MATTER-G6-02",  # Mixtures and Separation → Compounds and Mixtures
    "SCI-CHEM-G6-03": "SCI-MATTER-G6-04",  # Properties of Materials → Properties of Matter — Density and Solubility
    "SCI-CHEM-G6-04": "SCI-MATTER-G6-01",  # Atoms, Elements and Compounds → Atoms and Elements
    "SCI-CHEM-G6-05": "SCI-CHEM-CHANGE-G6-02",  # Acids and Alkalis → Acids and Alkalis
    "SCI-EARTH-G6-01": "SCI-FORCES-SPACE-G6-02",  # The Solar System → The Solar System and Orbits
    "SCI-EARTH-G6-02": "SCI-FORCES-SPACE-G6-03",  # Earth in Space / Seasons → Eclipses and Phases of the Moon
    "SCI-EARTH-G6-03": "SCI-MATTER-G6-04",  # The Water Cycle → Properties of Matter (water states context)
    "SCI-EARTH-G6-04": "SCI-FORCES-SPACE-G6-01",  # Rocks and the Rock Cycle → Gravity/Forces (closest G6 topic)
    "SCI-ENQ-G6-01": "SCI-ENQ-G6-01",  # Planning Investigations → Scientific Method and Hypotheses
    "SCI-ENQ-G6-02": "SCI-ENQ-G6-02",  # Recording and Presenting Data → Recording and Presenting Data
    "SCI-ENQ-G6-03": "SCI-ENQ-G6-03",  # Communicating Scientific Ideas → Drawing Conclusions and Evaluating
    "SCI-PHY-G6-01": "SCI-FORCES-SPACE-G6-01",  # Forces and Their Effects → Gravity as a Universal Force
    "SCI-PHY-G6-02": "SCI-ENERGY-SOUND-G6-01",  # Energy Forms and Transfer → Energy Types and Transfer
    "SCI-PHY-G6-03": "SCI-ENERGY-SOUND-G6-03",  # Electric Circuits → Electricity and Circuits
    "SCI-PHY-G6-04": "SCI-ENERGY-SOUND-G6-02",  # Sound — Vibrations, Pitch, Loudness → Sound — Vibrations, Frequency and Amplitude
    "SCI-PHY-G6-05": "SCI-FORCES-SPACE-G6-01",  # Magnets and Magnetic Fields → Gravity/Forces (closest G6)
    # ── GRADE 7 ──────────────────────────────────────────────────────────────
    "SCI-BIO-G7-01": "SCI-RESP-G7-02",  # Human Organ Systems → The Respiratory System (closest G7 human biology)
    "SCI-BIO-G7-02": "SCI-HUMAN-BIO-G8-04",  # Reproduction → Reproduction and Development (grade shift G7→G8, same content)
    "SCI-BIO-G7-03": "SCI-HEALTH-G7-01",  # Nutrition and Health → Nutrition and Balanced Diet
    "SCI-BIO-G7-04": "SCI-RESP-G7-01",  # Respiration — Aerobic and Anaerobic → Aerobic Respiration
    "SCI-BIO-G7-05": "SCI-HEALTH-G7-01",  # Digestive System and Nutrition → Nutrition and Balanced Diet
    "SCI-BIO-G7-06": "SCI-HEALTH-G7-02",  # Genetics — Introduction to Inheritance → Disease/Body Defences (closest)
    "SCI-CHEM-G7-01": "SCI-ATOM-REACT-G7-01",  # Atoms, Elements and the Periodic Table → Atomic Structure
    "SCI-CHEM-G7-02": "SCI-ATOM-REACT-G7-02",  # Chemical and Physical Changes → Types of Chemical Reactions
    "SCI-CHEM-G7-03": "SCI-ATOM-REACT-G7-02",  # Acids, Alkalis and Neutralisation → Types of Chemical Reactions
    "SCI-CHEM-G7-04": "SCI-GASES-LIQ-G7-01",  # Gases in the Atmosphere → Properties and Behaviour of Gases
    "SCI-CHEM-G7-05": "SCI-ATOM-REACT-G7-02",  # Acids, Bases and Salts → Types of Chemical Reactions
    "SCI-EARTH-G7-01": "SCI-EARTH-SOL-G7-02",  # The Solar System and Space Exploration → The Solar System and Beyond
    "SCI-EARTH-G7-02": "SCI-EARTH-SOL-G7-01",  # Earth's Structure and Tectonic Plates → Earth's Motions and the Seasons
    "SCI-EARTH-G7-03": "SCI-EARTH-SOL-G7-01",  # Weather and Climate → Earth's Motions and the Seasons
    "SCI-ENQ-G7-01": "SCI-ENQ-G7-01",  # Variables and Fair Testing → Variables and Experimental Design
    "SCI-ENQ-G7-02": "SCI-ENQ-G7-02",  # Analysing Evidence and Drawing Conclusions → Analysing Evidence
    "SCI-ENQ-G7-03": "SCI-ENQ-G7-03",  # Drawing Conclusions and Evaluating → Drawing Conclusions and Evaluating
    "SCI-PHY-G7-01": "SCI-LIGHT-G7-01",  # Light and Optics → Reflection and Refraction
    "SCI-PHY-G7-02": "SCI-WAVES-ENERGY-G8-02",  # Sound and Waves → Sound — Advanced (correct subject, grade shift)
    "SCI-PHY-G7-03": "SCI-EARTH-SOL-G7-02",  # Earth and Space (misplaced in PHY) → The Solar System and Beyond
    "SCI-PHY-G7-04": "SCI-MOTION-G7-01",  # Motion — Speed and Distance-Time Graphs → Speed and Distance-Time Graphs
    "SCI-PHY-G7-05": "SCI-MOTION-G7-03",  # Pressure in Liquids and Gases → Pressure
    # ── GRADE 8 ──────────────────────────────────────────────────────────────
    "SCI-BIO-G8-01": "SCI-ECOSYS-G8-02",  # Genetics and Inheritance → Adaptation and Natural Selection (closest)
    "SCI-BIO-G8-02": "SCI-HEALTH-G7-02",  # Disease and Immunity → Disease and the Body's Defences (grade shift G8→G7, same content)
    "SCI-BIO-G8-03": "SCI-RESP-G7-01",  # Respiration and Gas Exchange → Aerobic Respiration (grade shift G8→G7, same content)
    "SCI-BIO-G8-04": "SCI-ECOSYS-G8-01",  # Ecosystems and Biodiversity → Population Dynamics and Interdependence
    "SCI-BIO-G8-05": "SCI-ECOSYS-G8-02",  # Evolution and Natural Selection → Adaptation and Natural Selection
    "SCI-CHEM-G8-01": "SCI-CHEM-BOND-G8-04",  # The Periodic Table and Reactivity → The Periodic Table and Trends
    "SCI-CHEM-G8-02": "SCI-CHEM-REACT-G8-02",  # Rates of Reaction → Rates of Reaction
    "SCI-CHEM-G8-03": "SCI-CHEM-REACT-G8-01",  # Reversible Reactions → Reversible Reactions and Equilibrium
    "SCI-CHEM-G8-04": "SCI-CHEM-REACT-G8-03",  # Energy Changes in Reactions → Energy Changes in Reactions
    "SCI-CHEM-G8-05": "SCI-CHEM-REACT-G8-04",  # Organic Chemistry Introduction → Organic Chemistry Introduction
    "SCI-EARTH-G8-01": "SCI-EARTH-ADV-G8-03",  # Earth's Atmosphere and Climate Change → Earth's Atmosphere and Climate Change
    "SCI-EARTH-G8-02": "SCI-ECOSYS-G8-03",  # Earth's Resources and Sustainability → Human Impact and Conservation
    "SCI-EARTH-G8-03": "SCI-EARTH-ADV-G8-04",  # Space Science and Cosmology → Space Science and Cosmology
    "SCI-ENQ-G8-01": "SCI-ENQ-G8-01",  # Evaluating Investigations → Advanced Investigation Design
    "SCI-ENQ-G8-02": "SCI-ENQ-G8-01",  # Advanced Investigation Design → Advanced Investigation Design
    "SCI-ENQ-G8-03": "SCI-ENQ-G8-02",  # Ethical Dimensions of Science → Data Analysis and Statistical Reasoning
    "SCI-PHY-G8-01": "SCI-ELEC-ADV-G8-04",  # Electromagnetism → Electromagnetic Effects
    "SCI-PHY-G8-02": "SCI-WAVES-ENERGY-G8-01",  # Wave Properties → Wave Properties
    "SCI-PHY-G8-03": "SCI-MOTION-G7-02",  # Forces and Motion → Forces and Newton's Laws (correct subject, grade shift)
    "SCI-PHY-G8-04": "SCI-ELEC-ADV-G8-04",  # Electromagnetic Effects — Introduction → Electromagnetic Effects
    "SCI-PHY-G8-05": "SCI-EARTH-ADV-G8-04",  # Space Physics → Space Science and Cosmology
}

# Stale topic canonical codes to delete from curriculum_topics (cambridge_lower/SCI only)
STALE_TOPIC_CODES = ("SCI-BIO", "SCI-CHEM", "SCI-PHY", "SCI-EARTH")

# Pattern matching stale subtopic canonical codes (G6–G8 only, not G5 Primary)
STALE_SUBTOPIC_PATTERN = r"^SCI-(BIO|CHEM|PHY|EARTH)-G[678]-"


async def run_migration(dry_run: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            async with db.begin():
                # ── Step 1: Resolve old subtopic IDs → new subtopic IDs ───────
                log.info("resolving_subtopic_ids")
                old_codes = list(SUBTOPIC_REMAP.keys())

                rows = await db.execute(
                    text("SELECT id, canonical_code FROM subtopics WHERE canonical_code = ANY(:codes)"),
                    {"codes": old_codes},
                )
                old_id_map = {row.canonical_code: row.id for row in rows}

                new_codes = list(set(SUBTOPIC_REMAP.values()))
                rows = await db.execute(
                    text("SELECT id, canonical_code FROM subtopics WHERE canonical_code = ANY(:codes)"),
                    {"codes": new_codes},
                )
                new_id_map = {row.canonical_code: row.id for row in rows}

                # Check all new subtopics exist
                missing_new = [c for c in new_codes if c not in new_id_map]
                if missing_new:
                    log.error("missing_new_subtopics", codes=missing_new)
                    log.error("run_patch_curriculum_v3_first", hint="python -m scripts.patch_curriculum_v3")
                    return 1

                # ── Step 2: Count questions to be remapped ────────────────────
                old_ids_with_questions = []
                for old_code, old_id in old_id_map.items():
                    result = await db.execute(
                        text("SELECT COUNT(*) FROM question_bank WHERE subtopic_id = :id"),
                        {"id": old_id},
                    )
                    count = result.scalar()
                    if count > 0:
                        old_ids_with_questions.append((old_code, old_id, count))

                total_to_remap = sum(c for _, _, c in old_ids_with_questions)
                log.info("questions_to_remap", count=total_to_remap, subtopics=len(old_ids_with_questions))

                if dry_run:
                    log.info("dry_run — would remap:")
                    for old_code, _, count in old_ids_with_questions:
                        new_code = SUBTOPIC_REMAP[old_code]
                        log.info("would_remap", old=old_code, new=new_code, questions=count)
                    log.info("dry_run — would delete stale subtopics matching", pattern=STALE_SUBTOPIC_PATTERN)
                    log.info("dry_run — would delete stale curriculum_topics", topics=STALE_TOPIC_CODES)
                    return 0

                # ── Step 3: Update question_bank ──────────────────────────────
                log.info("updating_question_bank")
                total_updated = 0
                for old_code, old_id, _ in old_ids_with_questions:
                    new_code = SUBTOPIC_REMAP[old_code]
                    new_id = new_id_map[new_code]
                    result = await db.execute(
                        text("UPDATE question_bank SET subtopic_id = :new_id WHERE subtopic_id = :old_id"),
                        {"new_id": new_id, "old_id": old_id},
                    )
                    updated = result.rowcount
                    total_updated += updated
                    log.info("remapped", old=old_code, new=new_code, questions=updated)

                log.info("question_bank_updated", total=total_updated)

                # ── Step 4: Verify zero questions remain on old subtopics ──────
                remaining = await db.execute(
                    text("""
                        SELECT COUNT(*) FROM question_bank qb
                        JOIN subtopics st ON qb.subtopic_id = st.id
                        WHERE st.canonical_code ~ :pattern
                    """),
                    {"pattern": STALE_SUBTOPIC_PATTERN},
                )
                remaining_count = remaining.scalar()
                if remaining_count > 0:
                    log.error("questions_still_on_old_subtopics", count=remaining_count)
                    raise RuntimeError(f"{remaining_count} questions still on stale subtopics — aborting")
                log.info("verified_zero_questions_on_old_subtopics")

                # ── Step 5: Delete stale subtopics ────────────────────────────
                result = await db.execute(
                    text("DELETE FROM subtopics WHERE canonical_code ~ :pattern"),
                    {"pattern": STALE_SUBTOPIC_PATTERN},
                )
                log.info("deleted_stale_subtopics", count=result.rowcount)

                # ── Step 6: Delete stale curriculum_topics ────────────────────
                result = await db.execute(
                    text("""
                        DELETE FROM curriculum_topics ct
                        USING topics t, curricula c, subjects s
                        WHERE ct.topic_id = t.id
                          AND ct.curriculum_id = c.id
                          AND ct.subject_id = s.id
                          AND c.code = 'cambridge_lower'
                          AND s.code = 'SCI'
                          AND t.canonical_code = ANY(:codes)
                    """),
                    {"codes": list(STALE_TOPIC_CODES)},
                )
                log.info("deleted_stale_curriculum_topics", count=result.rowcount)

                # ── Step 7: Verify no orphan questions ────────────────────────
                orphans = await db.execute(
                    text("""
                        SELECT COUNT(*) FROM question_bank qb
                        LEFT JOIN subtopics st ON qb.subtopic_id = st.id
                        WHERE st.id IS NULL
                    """)
                )
                orphan_count = orphans.scalar()
                if orphan_count > 0:
                    log.error("orphan_questions_detected", count=orphan_count)
                    raise RuntimeError(f"{orphan_count} orphan questions found — rolling back")
                log.info("verified_zero_orphan_questions")

                # ── Step 8: Final summary ─────────────────────────────────────
                total_q = await db.execute(text("SELECT COUNT(*) FROM question_bank"))
                log.info(
                    "migration_complete",
                    questions_remapped=total_updated,
                    total_questions_in_db=total_q.scalar(),
                )

    except Exception as exc:
        log.error("migration_failed", error=str(exc), exc_info=True)
        await engine.dispose()
        return 1
    finally:
        await engine.dispose()

    return 0


async def main(dry_run: bool) -> int:
    log.info("remap_lower_sci_questions_start", dry_run=dry_run)
    return await run_migration(dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remap cambridge_lower SCI questions from old discipline-split topics to correct Cambridge 0893 integrated units."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be remapped without writing to the database.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
