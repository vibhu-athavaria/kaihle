"""Curriculum patch script — applies cambridge_v3.json additions to the database.

Reads cambridge_v3.json and inserts any topics/subtopics that are not yet in the
database. Skips all rows that already exist (identified by canonical_code).
Safe to run multiple times — fully idempotent.

Works with any DATABASE_URL: dev Docker (port 5433) or prod Render.com.

Usage (from project root):
    # With Docker running:
    docker compose exec backend python -m scripts.patch_curriculum_v3

    # With a custom data file:
    docker compose exec backend python -m scripts.patch_curriculum_v3 \
        --data-file backend/data/curriculum/cambridge_v3.json

    # Dry run (validates JSON, shows what would be inserted — no DB writes):
    docker compose exec backend python -m scripts.patch_curriculum_v3 --dry-run

    # Outside Docker (requires DATABASE_URL in env):
    cd backend
    DATABASE_URL=postgresql+asyncpg://... python -m scripts.patch_curriculum_v3

Insert order (respects FK dependencies):
    curricula → subjects → grades → curriculum_subjects
    → topics → curriculum_topics → subtopics → subtopic_prerequisites
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
DEFAULT_DATA_FILE = _BACKEND_ROOT / "data" / "curriculum" / "cambridge_v3.json"


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
            "patch_complete",
            new_curricula=self.curricula,
            new_subjects=self.subjects,
            new_grades=self.grades,
            new_curriculum_subjects=self.curriculum_subjects,
            new_topics=self.topics,
            new_curriculum_topics=self.curriculum_topics,
            new_subtopics=self.subtopics,
            new_prerequisites=self.prerequisites,
            skipped_existing=self.skipped,
            warnings=len(self.warnings),
        )
        if self.warnings:
            log.warning("patch_warnings", count=len(self.warnings))
            for w in self.warnings:
                log.warning("warning", detail=w)


# ---------------------------------------------------------------------------
# Core patcher — same idempotent get-or-create pattern as seed_curriculum_graph.py
# ---------------------------------------------------------------------------
class CurriculumPatcher:
    """Applies v3 curriculum data to the DB, skipping rows that already exist."""

    def __init__(self, db: AsyncSession, stats: Stats, dry_run: bool = False) -> None:
        self.db = db
        self.stats = stats
        self.dry_run = dry_run

        self._curriculum_ids: dict[str, uuid.UUID] = {}  # code → id
        self._subject_ids: dict[str, uuid.UUID] = {}  # code → id
        self._grade_ids: dict[int, uuid.UUID] = {}  # level → id
        self._topic_ids: dict[str, uuid.UUID] = {}  # canonical_code → id

    # ── Generic helpers ─────────────────────────────────────────────────

    async def _get_or_create_curriculum(self, data: dict) -> uuid.UUID:
        if self.dry_run:
            new_id = uuid.uuid4()
            log.debug("dry_run_would_insert", table="curricula", code=data["code"])
            self._curriculum_ids[data["code"]] = new_id
            self.stats.curricula += 1
            return new_id

        result = await self.db.execute(select(Curriculum).where(Curriculum.code == data["code"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

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
        log.info("inserted_curriculum", code=data["code"])
        return row.id

    async def _get_or_create_subject(self, data: dict) -> uuid.UUID:
        if self.dry_run:
            new_id = uuid.uuid4()
            self._subject_ids[data["code"]] = new_id
            self.stats.subjects += 1
            return new_id

        result = await self.db.execute(select(Subject).where(Subject.code == data["code"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

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
        log.info("inserted_subject", code=data["code"])
        return row.id

    async def _get_or_create_grade(self, data: dict) -> uuid.UUID:
        if self.dry_run:
            new_id = uuid.uuid4()
            self._grade_ids[data["level"]] = new_id
            self.stats.grades += 1
            return new_id

        result = await self.db.execute(select(Grade).where(Grade.level == data["level"]))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

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
        log.info("inserted_grade", level=data["level"])
        return row.id

    async def _get_or_create_curriculum_subject(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        is_core: bool,
        sort_order: int | None,
    ) -> None:
        if self.dry_run:
            self.stats.curriculum_subjects += 1
            return

        result = await self.db.execute(
            select(CurriculumSubject).where(
                CurriculumSubject.curriculum_id == curriculum_id,
                CurriculumSubject.subject_id == subject_id,
            )
        )
        if result.scalar_one_or_none():
            self.stats.skipped += 1
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
        canonical_code = data["canonical_code"]
        if self.dry_run:
            new_id = uuid.uuid4()
            self._topic_ids[canonical_code] = new_id
            self.stats.topics += 1
            return new_id

        result = await self.db.execute(select(Topic).where(Topic.canonical_code == canonical_code))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        row = Topic(
            id=uuid.uuid4(),
            name=data["name"],
            canonical_code=canonical_code,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.topics += 1
        log.info("inserted_topic", canonical_code=canonical_code)
        return row.id

    async def _get_or_create_curriculum_topic(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        grade_id: uuid.UUID,
        topic_id: uuid.UUID,
        data: dict,
    ) -> uuid.UUID:
        if self.dry_run:
            new_id = uuid.uuid4()
            self.stats.curriculum_topics += 1
            return new_id

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

    _DIFFICULTY_STR_MAP: dict[str, int] = {
        "easy": 1,
        "low": 1,
        "beginner": 1,
        "medium": 3,
        "moderate": 3,
        "hard": 4,
        "difficult": 4,
        "high": 4,
        "advanced": 5,
        "expert": 5,
    }

    def _coerce_difficulty(self, value: int | str | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        return self._DIFFICULTY_STR_MAP.get(str(value).lower(), 3)

    async def _get_or_create_subtopic(
        self,
        curriculum_topic_id: uuid.UUID,
        data: dict,
    ) -> uuid.UUID:
        canonical_code = data["canonical_code"]
        if self.dry_run:
            new_id = uuid.uuid4()
            self.stats.subtopics += 1
            return new_id

        result = await self.db.execute(select(Subtopic).where(Subtopic.canonical_code == canonical_code))
        existing = result.scalar_one_or_none()
        if existing:
            self.stats.skipped += 1
            return existing.id

        row = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=curriculum_topic_id,
            name=data["name"],
            canonical_code=canonical_code,
            learning_objective=data["learning_objective"],
            bloom_taxonomy_level=data.get("bloom_taxonomy_level"),
            difficulty_level=self._coerce_difficulty(data.get("difficulty_level")),
            estimated_minutes=data.get("estimated_minutes"),
            sequence_order=data.get("sequence_order"),
            embedding=None,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.subtopics += 1
        log.info("inserted_subtopic", canonical_code=canonical_code)
        return row.id

    async def _insert_prerequisite(
        self,
        subtopic_id: uuid.UUID,
        prerequisite_id: uuid.UUID,
    ) -> None:
        if self.dry_run:
            self.stats.prerequisites += 1
            return

        result = await self.db.execute(
            select(SubtopicPrerequisite).where(
                SubtopicPrerequisite.subtopic_id == subtopic_id,
                SubtopicPrerequisite.prerequisite_subtopic_id == prerequisite_id,
            )
        )
        if result.scalar_one_or_none():
            self.stats.skipped += 1
            return

        row = SubtopicPrerequisite(
            subtopic_id=subtopic_id,
            prerequisite_subtopic_id=prerequisite_id,
            importance="REQUIRED",
        )
        self.db.add(row)
        await self.db.flush()
        self.stats.prerequisites += 1

    # ── Main patch orchestrator ──────────────────────────────────────────

    async def patch(self, data: dict) -> None:
        """Apply all curriculum data in FK dependency order."""

        # ── 1. Curricula ────────────────────────────────────────────────
        log.info("patching_curricula", count=len(data["curricula"]))
        for c in data["curricula"]:
            cid = await self._get_or_create_curriculum(c)
            self._curriculum_ids[c["code"]] = cid

        # ── 2. Subjects ─────────────────────────────────────────────────
        log.info("patching_subjects", count=len(data["subjects"]))
        for s in data["subjects"]:
            sid = await self._get_or_create_subject(s)
            self._subject_ids[s["code"]] = sid

        # ── 3. Grades ───────────────────────────────────────────────────
        log.info("patching_grades", count=len(data["grades"]))
        for g in data["grades"]:
            gid = await self._get_or_create_grade(g)
            self._grade_ids[g["level"]] = gid

        # ── 4. Curriculum → Subject bindings ────────────────────────────
        log.info("patching_curriculum_subjects", count=len(data["curriculum_subjects"]))
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
        log.info("patching_curriculum_tree", entries=len(data["curriculum_tree"]))

        subtopics_for_prereq: dict[
            tuple[str, str, int],
            list[tuple[dict, uuid.UUID]],
        ] = {}

        for entry in data["curriculum_tree"]:
            curriculum_code = entry["curriculum_code"]
            subject_code = entry["subject_code"]
            grade_level = entry["grade_level"]

            curriculum_id = self._curriculum_ids.get(curriculum_code)
            subject_id = self._subject_ids.get(subject_code)
            grade_id = self._grade_ids.get(grade_level)

            if not curriculum_id or not subject_id or not grade_id:
                msg = (
                    f"Skipping tree entry {curriculum_code}/{subject_code}/G{grade_level}: "
                    f"missing FK (curriculum={curriculum_id}, subject={subject_id}, grade={grade_id})"
                )
                self.stats.warnings.append(msg)
                log.warning("tree_entry_skipped_missing_fk", detail=msg)
                continue

            entry_key = (curriculum_code, subject_code, grade_level)
            entry_subtopics: list[tuple[dict, uuid.UUID]] = []

            log.debug(
                "patching_tree_entry",
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
        log.info("resolving_prerequisites")

        global_subtopic_map: dict[str, uuid.UUID] = {}
        for subtopic_pairs in subtopics_for_prereq.values():
            for sd, sid in subtopic_pairs:
                global_subtopic_map[sd["name"]] = sid
                if sd.get("canonical_code"):
                    global_subtopic_map[sd["canonical_code"]] = sid

        for entry_key, subtopic_pairs in subtopics_for_prereq.items():
            curriculum_code, subject_code, grade_level = entry_key

            for subtopic_data, subtopic_id in subtopic_pairs:
                prereq_refs: list[str] = subtopic_data.get("prerequisites", [])
                for ref in prereq_refs:
                    prereq_id = global_subtopic_map.get(ref)
                    if prereq_id is None:
                        # Prerequisite might exist in DB from a previous seed run.
                        # Attempt a DB lookup by canonical_code before giving up.
                        if not self.dry_run:
                            db_result = await self.db.execute(select(Subtopic).where(Subtopic.canonical_code == ref))
                            db_subtopic = db_result.scalar_one_or_none()
                            if db_subtopic:
                                prereq_id = db_subtopic.id

                    if prereq_id is None:
                        msg = (
                            f"Prerequisite '{ref}' not found for subtopic "
                            f"'{subtopic_data['name']}' "
                            f"({curriculum_code}/{subject_code}/G{grade_level}). "
                            "Skipping — check JSON for typos."
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
# Validation — same rules as seed_curriculum_graph.py
# ---------------------------------------------------------------------------
def validate_json(data: dict) -> list[str]:
    """Validate JSON structure before touching the DB. Returns list of errors."""
    errors: list[str] = []

    required_keys = ["curricula", "subjects", "grades", "curriculum_subjects", "curriculum_tree"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing top-level key: '{key}'")

    if errors:
        return errors

    for i, entry in enumerate(data.get("curriculum_tree", [])):
        for field in ["curriculum_code", "subject_code", "grade_level", "topics"]:
            if field not in entry:
                errors.append(f"curriculum_tree[{i}] missing field '{field}'")

        if "grade_level" in entry and not isinstance(entry["grade_level"], int):
            errors.append(
                f"curriculum_tree[{i}] grade_level must be an integer, got {type(entry['grade_level']).__name__}"
            )

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
    log.info("patch_curriculum_v3_start", data_file=str(data_file), dry_run=dry_run)

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
        patcher = CurriculumPatcher(db=None, stats=stats, dry_run=True)  # type: ignore[arg-type]
        await patcher.patch(data)
        stats.report()
        return 0

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    stats = Stats()
    try:
        async with async_session() as db:
            patcher = CurriculumPatcher(db=db, stats=stats)
            await patcher.patch(data)
    except Exception as exc:
        log.error("patch_failed", error=str(exc), exc_info=True)
        await engine.dispose()
        return 1
    finally:
        await engine.dispose()

    stats.report()

    if stats.warnings:
        log.warning(
            "completed_with_warnings",
            warning_count=len(stats.warnings),
            hint="Check warnings above. Unresolved prerequisites are not fatal.",
        )

    log.info("patch_curriculum_v3_done")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply cambridge_v3.json curriculum additions to the database.")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help=f"Path to the v3 curriculum JSON file (default: {DEFAULT_DATA_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate JSON and simulate inserts without writing to the database.",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main(data_file=args.data_file, dry_run=args.dry_run)))
