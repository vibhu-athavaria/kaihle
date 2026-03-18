"""Curriculum graph seeding script.

Seeds the full Cambridge curriculum hierarchy from cambridge_v1.json into the database.
Must run before M1-1-T1 (question import) and M1-2-T2 (PDF ingestion).

Usage (from project root):
    # With Docker running:
    docker compose exec backend python -m scripts.seed_curriculum_graph

    # With a custom data file:
    docker compose exec backend python -m scripts.seed_curriculum_graph \
        --data-file backend/data/curriculum/cambridge_v1.json

    # Dry run (validates JSON only, no DB writes):
    docker compose exec backend python -m scripts.seed_curriculum_graph --dry-run

    # Outside Docker (requires DATABASE_URL in env):
    cd backend
    python -m scripts.seed_curriculum_graph

Insert order (respects FK dependencies):
    curricula → subjects → grades → curriculum_subjects
    → topics → curriculum_topics → subtopics → subtopic_prerequisites

Idempotent: re-running on an already-seeded database produces zero new inserts.
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap path so we can import app modules when run as a script
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.models.curriculum import (  # noqa: E402
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    SubtopicPrerequisite,
    Topic,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Default data file path
# ---------------------------------------------------------------------------
DEFAULT_DATA_FILE = _BACKEND_ROOT / "data" / "curriculum" / "cambridge_v1.json"


# ---------------------------------------------------------------------------
# Counters for final stats report
# ---------------------------------------------------------------------------
class Stats:
    def __init__(self) -> None:
        self.curricula = 0
        self.subjects = 0
        self.grades = 0
        self.curriculum_subjects = 0
        self.topics = 0
        self.curriculum_topics = 0
        self.subtopics = 0
        self.prerequisites = 0
        self.skipped = 0
        self.warnings: list[str] = []

    def report(self) -> None:
        log.info(
            "seed_complete",
            curricula=self.curricula,
            subjects=self.subjects,
            grades=self.grades,
            curriculum_subjects=self.curriculum_subjects,
            topics=self.topics,
            curriculum_topics=self.curriculum_topics,
            subtopics=self.subtopics,
            prerequisites=self.prerequisites,
            skipped_existing=self.skipped,
            warnings=len(self.warnings),
        )
        if self.warnings:
            log.warning("seed_warnings", count=len(self.warnings))
            for w in self.warnings:
                log.warning("warning", detail=w)


# ---------------------------------------------------------------------------
# Core seeder
# ---------------------------------------------------------------------------
class CurriculumSeeder:
    """Seeds curriculum hierarchy from a cambridge_v1.json file."""

    def __init__(self, db: AsyncSession, stats: Stats, dry_run: bool = False) -> None:
        self.db = db
        self.stats = stats
        self.dry_run = dry_run

        # In-memory lookup tables built as we insert — avoids N+1 DB queries
        # for FK resolution within the same run.
        self._curriculum_ids: dict[str, uuid.UUID] = {}  # code → id
        self._subject_ids: dict[str, uuid.UUID] = {}  # code → id
        self._grade_ids: dict[int, uuid.UUID] = {}  # level → id
        self._topic_ids: dict[str, uuid.UUID] = {}  # canonical_code → id
        # subtopic name→id scoped per (curriculum_code, subject_code, grade_level)
        # Used for prerequisite resolution — prerequisite values in JSON are names
        self._subtopic_name_map: dict[tuple[str, str, int], dict[str, uuid.UUID]] = {}

    # ── Generic helpers ─────────────────────────────────────────────────

    async def _get_or_create_curriculum(self, data: dict) -> uuid.UUID:
        """Fetch existing or insert new Curriculum row. Returns its UUID."""
        result = await self.db.execute(select(Curriculum).where(Curriculum.code == data["code"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            log.debug("dry_run_would_insert", table="curricula", code=data["code"])
            self._curriculum_ids[data["code"]] = new_id
            self.stats.curricula += 1
            return new_id

        row = Curriculum(
            id=uuid.uuid4(),
            code=data["code"],
            name=data["name"],
            description=data.get("description"),
            country=data.get("country"),
            is_active=data.get("is_active", True),
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.curricula += 1
        log.debug("inserted_curriculum", code=data["code"], id=str(row.id))
        return row.id

    async def _get_or_create_subject(self, data: dict) -> uuid.UUID:
        result = await self.db.execute(select(Subject).where(Subject.code == data["code"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            self._subject_ids[data["code"]] = new_id
            self.stats.subjects += 1
            return new_id

        row = Subject(
            id=uuid.uuid4(),
            code=data["code"],
            name=data["name"],
            description=data.get("description"),
            icon=data.get("icon"),
            color=data.get("color"),
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.subjects += 1
        log.debug("inserted_subject", code=data["code"], id=str(row.id))
        return row.id

    async def _get_or_create_grade(self, data: dict) -> uuid.UUID:
        result = await self.db.execute(select(Grade).where(Grade.level == data["level"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            self._grade_ids[data["level"]] = new_id
            self.stats.grades += 1
            return new_id

        row = Grade(
            id=uuid.uuid4(),
            level=data["level"],
            name=data["name"],
            description=data.get("description"),
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.grades += 1
        log.debug("inserted_grade", level=data["level"], id=str(row.id))
        return row.id

    async def _get_or_create_curriculum_subject(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        is_core: bool,
        sort_order: int | None,
    ) -> None:
        result = await self.db.execute(
            select(CurriculumSubject).where(
                CurriculumSubject.curriculum_id == curriculum_id,
                CurriculumSubject.subject_id == subject_id,
            )
        )
        if result.scalar_one_or_none():
            self.stats.skipped += 1
            return

        if self.dry_run:
            self.stats.curriculum_subjects += 1
            return

        row = CurriculumSubject(
            curriculum_id=curriculum_id,
            subject_id=subject_id,
            is_core=is_core,
            sort_order=sort_order,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.curriculum_subjects += 1

    async def _get_or_create_topic(self, data: dict) -> uuid.UUID:
        """Topics are curriculum-agnostic. Deduplicate on canonical_code."""
        canonical_code = data["canonical_code"]
        result = await self.db.execute(select(Topic).where(Topic.canonical_code == canonical_code))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            self._topic_ids[canonical_code] = new_id
            self.stats.topics += 1
            return new_id

        row = Topic(
            id=uuid.uuid4(),
            name=data["name"],
            canonical_code=canonical_code,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.topics += 1
        log.debug("inserted_topic", canonical_code=canonical_code, id=str(row.id))
        return row.id

    async def _get_or_create_curriculum_topic(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        grade_id: uuid.UUID,
        topic_id: uuid.UUID,
        data: dict,
    ) -> uuid.UUID:
        result = await self.db.execute(
            select(CurriculumTopic).where(
                CurriculumTopic.curriculum_id == curriculum_id,
                CurriculumTopic.subject_id == subject_id,
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.topic_id == topic_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            self.stats.curriculum_topics += 1
            return new_id

        row = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum_id,
            subject_id=subject_id,
            grade_id=grade_id,
            topic_id=topic_id,
            sequence_order=data.get("sequence_order"),
            learning_objectives=data.get("learning_objectives"),
            recommended_weeks=data.get("recommended_weeks"),
            is_required=True,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.curriculum_topics += 1
        return row.id

    async def _get_or_create_subtopic(
        self,
        curriculum_topic_id: uuid.UUID,
        data: dict,
    ) -> uuid.UUID:
        canonical_code = data["canonical_code"]
        result = await self.db.execute(select(Subtopic).where(Subtopic.canonical_code == canonical_code))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        if self.dry_run:
            new_id = uuid.uuid4()
            self.stats.subtopics += 1
            return new_id

        row = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=curriculum_topic_id,
            name=data["name"],
            canonical_code=canonical_code,
            learning_objective=data["learning_objective"],
            bloom_taxonomy_level=data.get("bloom_taxonomy_level"),
            difficulty_level=data.get("difficulty_level"),
            estimated_minutes=data.get("estimated_minutes"),
            sequence_order=data.get("sequence_order"),
            embedding=None,  # Populated by M1-2-T2 (curriculum PDF ingestion)
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.subtopics += 1
        log.debug("inserted_subtopic", canonical_code=canonical_code, id=str(row.id))
        return row.id

    async def _insert_prerequisite(
        self,
        subtopic_id: uuid.UUID,
        prerequisite_id: uuid.UUID,
    ) -> None:
        result = await self.db.execute(
            select(SubtopicPrerequisite).where(
                SubtopicPrerequisite.subtopic_id == subtopic_id,
                SubtopicPrerequisite.prerequisite_subtopic_id == prerequisite_id,
            )
        )
        if result.scalar_one_or_none():
            self.stats.skipped += 1
            return

        if self.dry_run:
            self.stats.prerequisites += 1
            return

        row = SubtopicPrerequisite(
            subtopic_id=subtopic_id,
            prerequisite_subtopic_id=prerequisite_id,
            importance="REQUIRED",
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.prerequisites += 1

    # ── Main seed orchestrator ───────────────────────────────────────────

    async def seed(self, data: dict) -> None:
        """Seed all tables in FK dependency order."""

        # ── 1. Curricula ────────────────────────────────────────────────
        log.info("seeding_curricula", count=len(data["curricula"]))
        for c in data["curricula"]:
            cid = await self._get_or_create_curriculum(c)
            self._curriculum_ids[c["code"]] = cid

        # ── 2. Subjects ─────────────────────────────────────────────────
        log.info("seeding_subjects", count=len(data["subjects"]))
        for s in data["subjects"]:
            sid = await self._get_or_create_subject(s)
            self._subject_ids[s["code"]] = sid

        # ── 3. Grades ───────────────────────────────────────────────────
        log.info("seeding_grades", count=len(data["grades"]))
        for g in data["grades"]:
            gid = await self._get_or_create_grade(g)
            self._grade_ids[g["level"]] = gid

        # ── 4. Curriculum → Subject bindings ────────────────────────────
        log.info("seeding_curriculum_subjects", count=len(data["curriculum_subjects"]))
        for cs in data["curriculum_subjects"]:
            curriculum_id = self._curriculum_ids[cs["curriculum_code"]]
            subject_id = self._subject_ids[cs["subject_code"]]
            await self._get_or_create_curriculum_subject(
                curriculum_id=curriculum_id,
                subject_id=subject_id,
                is_core=cs.get("is_core", True),
                sort_order=cs.get("sort_order"),
            )

        # ── 5. Curriculum tree: topics → curriculum_topics → subtopics ──
        #
        # Each entry in curriculum_tree is ONE (curriculum, subject, grade) combination.
        # grade_level is a singular integer (not an array — see _meta.format_note).
        #
        # We collect subtopic name→id maps per entry for prerequisite resolution.
        # Prerequisites in the JSON are subtopic NAMES (not canonical codes).

        log.info("seeding_curriculum_tree", entries=len(data["curriculum_tree"]))

        # Collect all (subtopic_data, subtopic_id) pairs for prerequisite pass
        # after all subtopics are inserted.
        # Key: (curriculum_code, subject_code, grade_level)
        # Value: list of (subtopic_data_dict, inserted_subtopic_id)
        subtopics_for_prereq: dict[
            tuple[str, str, int],
            list[tuple[dict, uuid.UUID]],
        ] = {}

        for entry in data["curriculum_tree"]:
            curriculum_code = entry["curriculum_code"]
            subject_code = entry["subject_code"]
            grade_level = entry["grade_level"]  # singular int, per _meta.format_note

            curriculum_id = self._curriculum_ids.get(curriculum_code)
            subject_id = self._subject_ids.get(subject_code)
            grade_id = self._grade_ids.get(grade_level)

            if not curriculum_id or not subject_id or not grade_id:
                msg = (
                    f"Skipping tree entry {curriculum_code}/{subject_code}/G{grade_level}: "
                    f"curriculum_id={curriculum_id}, subject_id={subject_id}, grade_id={grade_id}"
                )
                self.stats.warnings.append(msg)
                log.warning("tree_entry_skipped_missing_fk", detail=msg)
                continue

            entry_key = (curriculum_code, subject_code, grade_level)
            entry_subtopics: list[tuple[dict, uuid.UUID]] = []

            log.debug(
                "seeding_tree_entry",
                curriculum=curriculum_code,
                subject=subject_code,
                grade=grade_level,
                topics=len(entry.get("topics", [])),
            )

            for topic_data in entry.get("topics", []):
                topic_id = await self._get_or_create_topic(topic_data)

                curriculum_topic_id = await self._get_or_create_curriculum_topic(
                    curriculum_id=curriculum_id,
                    subject_id=subject_id,
                    grade_id=grade_id,
                    topic_id=topic_id,
                    data=topic_data,
                )

                for subtopic_data in topic_data.get("subtopics", []):
                    subtopic_id = await self._get_or_create_subtopic(
                        curriculum_topic_id=curriculum_topic_id,
                        data=subtopic_data,
                    )
                    entry_subtopics.append((subtopic_data, subtopic_id))

            subtopics_for_prereq[entry_key] = entry_subtopics

        # ── 6. Prerequisite resolution ───────────────────────────────────
        #
        # Prerequisites are stored as subtopic NAMES in the JSON.
        # Resolve within each (curriculum, subject, grade) scope.
        # Log a warning and skip if a name doesn't resolve — do not crash.

        log.info("resolving_prerequisites")

        for entry_key, subtopic_pairs in subtopics_for_prereq.items():
            curriculum_code, subject_code, grade_level = entry_key

            # Build name→id map for this entry
            name_to_id: dict[str, uuid.UUID] = {sd["name"]: sid for sd, sid in subtopic_pairs}

            for subtopic_data, subtopic_id in subtopic_pairs:
                prereq_names: list[str] = subtopic_data.get("prerequisites", [])
                for prereq_name in prereq_names:
                    prereq_id = name_to_id.get(prereq_name)
                    if prereq_id is None:
                        msg = (
                            f"Prerequisite '{prereq_name}' not found for subtopic "
                            f"'{subtopic_data['name']}' "
                            f"({curriculum_code}/{subject_code}/G{grade_level}). "
                            f"Skipping — check JSON for typos."
                        )
                        self.stats.warnings.append(msg)
                        log.warning("prerequisite_not_resolved", detail=msg)
                        continue

                    await self._insert_prerequisite(
                        subtopic_id=subtopic_id,
                        prerequisite_id=prereq_id,
                    )

        # ── 7. Commit ────────────────────────────────────────────────────
        if not self.dry_run:
            await self.db.commit()
            log.info("committed")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_json(data: dict) -> list[str]:
    """Validate JSON structure before touching the DB. Returns list of errors."""
    errors: list[str] = []

    required_keys = ["curricula", "subjects", "grades", "curriculum_subjects", "curriculum_tree"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing top-level key: '{key}'")

    if errors:
        return errors  # can't validate further without top-level keys

    # Check every curriculum_tree entry has required fields
    for i, entry in enumerate(data.get("curriculum_tree", [])):
        for field in ["curriculum_code", "subject_code", "grade_level", "topics"]:
            if field not in entry:
                errors.append(f"curriculum_tree[{i}] missing field '{field}'")

        # Check grade_level is an int (not a list — common mistake)
        if "grade_level" in entry and not isinstance(entry["grade_level"], int):
            errors.append(
                f"curriculum_tree[{i}] grade_level must be an integer, got {type(entry['grade_level']).__name__}"
            )

        # Check every subtopic has learning_objective (NOT NULL in DB)
        for j, topic in enumerate(entry.get("topics", [])):
            for k, st in enumerate(topic.get("subtopics", [])):
                if not st.get("learning_objective"):
                    errors.append(
                        f"curriculum_tree[{i}].topics[{j}].subtopics[{k}] "
                        f"('{st.get('name')}') missing 'learning_objective'"
                    )
                if not st.get("canonical_code"):
                    errors.append(
                        f"curriculum_tree[{i}].topics[{j}].subtopics[{k}] ('{st.get('name')}') missing 'canonical_code'"
                    )

    # Check referenced codes exist
    curricula_codes = {c["code"] for c in data.get("curricula", [])}
    subject_codes = {s["code"] for s in data.get("subjects", [])}

    for cs in data.get("curriculum_subjects", []):
        if cs.get("curriculum_code") not in curricula_codes:
            errors.append(f"curriculum_subjects: unknown curriculum_code '{cs.get('curriculum_code')}'")
        if cs.get("subject_code") not in subject_codes:
            errors.append(f"curriculum_subjects: unknown subject_code '{cs.get('subject_code')}'")

    for entry in data.get("curriculum_tree", []):
        if entry.get("curriculum_code") not in curricula_codes:
            errors.append(f"curriculum_tree: unknown curriculum_code '{entry.get('curriculum_code')}'")
        if entry.get("subject_code") not in subject_codes:
            errors.append(f"curriculum_tree: unknown subject_code '{entry.get('subject_code')}'")

    return errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main(data_file: Path, dry_run: bool) -> int:
    """Main entry point. Returns exit code (0 = success, 1 = failure)."""

    log.info("seed_curriculum_graph_start", data_file=str(data_file), dry_run=dry_run)

    # Load JSON
    if not data_file.exists():
        log.error("data_file_not_found", path=str(data_file))
        return 1

    with data_file.open() as f:
        data = json.load(f)

    log.info(
        "json_loaded",
        curricula=len(data.get("curricula", [])),
        subjects=len(data.get("subjects", [])),
        grades=len(data.get("grades", [])),
        curriculum_subjects=len(data.get("curriculum_subjects", [])),
        tree_entries=len(data.get("curriculum_tree", [])),
    )

    # Validate before touching DB
    errors = validate_json(data)
    if errors:
        log.error("validation_failed", error_count=len(errors))
        for err in errors:
            log.error("validation_error", detail=err)
        return 1

    log.info("validation_passed")

    if dry_run:
        log.info("dry_run_mode_no_db_writes")
        stats = Stats()
        seeder = CurriculumSeeder(db=None, stats=stats, dry_run=True)  # type: ignore[arg-type]
        await seeder.seed(data)
        stats.report()
        return 0

    # Connect to DB — use new_event_loop-safe pattern
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    stats = Stats()
    try:
        async with async_session() as db:
            seeder = CurriculumSeeder(db=db, stats=stats)
            await seeder.seed(data)
    except Exception as exc:
        log.error("seed_failed", error=str(exc), exc_info=True)
        await engine.dispose()
        return 1
    finally:
        await engine.dispose()

    stats.report()

    # Exit non-zero if there were warnings (unresolved prerequisites etc.)
    if stats.warnings:
        log.warning(
            "completed_with_warnings",
            warning_count=len(stats.warnings),
            hint="Check the warnings above. Unresolved prerequisites are not fatal but should be investigated.",
        )
        return 0  # Still success — warnings don't fail the seed

    log.info("seed_curriculum_graph_done")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Cambridge curriculum graph into the database.")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help=f"Path to the curriculum JSON file (default: {DEFAULT_DATA_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate JSON and simulate inserts without writing to the database.",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(data_file=args.data_file, dry_run=args.dry_run))
    sys.exit(exit_code)
