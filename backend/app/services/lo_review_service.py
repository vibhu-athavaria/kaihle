"""KaihleAdmin review queue for curriculum-mapping decisions.

The remap pipeline resolves what it can automatically and stops where it cannot: an
embedding similarity in the ambiguous band, or an adjudicating model that declined to
choose. Those cases are curriculum judgements — "does this old objective assess the
same skill as this new one?" — and belong with an educator, not an engineer reading
JSON out of a backups directory.

Approving an item binds every question it governs in one action. That is the whole
economy of the design: the 2278 questions orphaned by the cambridge_v2 remap came from
71 old subtopics, so a reviewer makes 71 decisions rather than 2278.

Items are curriculum-scoped and carry no school_id — one ruling applies everywhere.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import structlog
from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.router import complete
from app.ai.similarity import cosine_similarity, embed_all, parse_vector
from app.models.curriculum import LearningObjective, LearningObjectiveReviewItem, QuestionBank

logger = structlog.get_logger()

ITEM_TYPE_QUESTION_REMAP = "QUESTION_REMAP"
STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_SPLIT = "SPLIT"

# Sequential adjudication of a large group would take minutes and time out the request.
# Bounded concurrency keeps a 100-question split to roughly half a minute while staying
# well inside provider rate limits.
_SPLIT_CONCURRENCY = 8

# Objectives offered per question. Enough for a real choice, few enough that the model
# is comparing rather than scanning a catalogue.
_SPLIT_SHORTLIST_SIZE = 4

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)  # noqa: S701


class LoReviewService:
    """Business logic for the learning-objective review queue."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_items(
        self,
        status_filter: str = STATUS_PENDING,
        item_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return a page of review items, largest blast radius first.

        Ordered by question_count descending so a reviewer with limited time spends it
        where a decision affects the most questions.
        """
        conditions = [LearningObjectiveReviewItem.status == status_filter]
        if item_type:
            conditions.append(LearningObjectiveReviewItem.item_type == item_type)

        total = await self.db.execute(select(func.count()).select_from(LearningObjectiveReviewItem).where(*conditions))
        rows = await self.db.execute(
            select(LearningObjectiveReviewItem)
            .where(*conditions)
            .order_by(
                LearningObjectiveReviewItem.question_count.desc(),
                LearningObjectiveReviewItem.source_code,
            )
            .limit(limit)
            .offset(offset)
        )
        items = list(rows.scalars().all())

        return {
            "total": int(total.scalar_one()),
            "items": [self._serialise(item) for item in items],
        }

    async def counts_by_status(self) -> dict[str, int]:
        """Queue summary for the admin dashboard badge."""
        rows = await self.db.execute(
            select(LearningObjectiveReviewItem.status, func.count()).group_by(LearningObjectiveReviewItem.status)
        )
        counts = {row[0]: int(row[1]) for row in rows.all()}
        for state in (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_SPLIT):
            counts.setdefault(state, 0)
        return counts

    async def approve_item(
        self,
        item_id: uuid.UUID,
        objective_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        admin_note: str | None = None,
    ) -> dict[str, Any]:
        """Bind the item's questions to the chosen objective and close it.

        The reviewer may pick any objective, not only a listed candidate — the
        candidates are the machine's shortlist, and an educator who knows the
        curriculum may well know better.
        """
        item = await self._get_pending(item_id)

        objective = await self.db.execute(select(LearningObjective).where(LearningObjective.id == objective_id))
        if objective.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Learning objective {objective_id} not found",
            )

        bound = 0
        if item.question_ids:
            # Only fill NULLs. If a question was bound by some other route in the
            # meantime, that binding stands rather than being silently overwritten.
            result = await self.db.execute(
                update(QuestionBank)
                .where(
                    QuestionBank.id.in_([uuid.UUID(q) for q in item.question_ids]),
                    QuestionBank.learning_objective_id.is_(None),
                )
                .values(learning_objective_id=objective_id)
            )
            bound = cast("CursorResult[Any]", result).rowcount or 0

        item.status = STATUS_APPROVED
        item.chosen_objective_id = objective_id
        item.resolved_by = reviewer_id
        item.resolved_at = datetime.now(UTC)
        item.admin_note = admin_note
        await self.db.commit()

        logger.info(
            "lo_review_item_approved",
            item_id=str(item_id),
            source_code=item.source_code,
            objective_id=str(objective_id),
            questions_bound=bound,
            followed_llm_suggestion=item.llm_suggested_code is not None
            and any(
                c.get("canonical_code") == item.llm_suggested_code and c.get("objective_id") == str(objective_id)
                for c in item.candidates
            ),
            reviewer_id=str(reviewer_id),
        )
        return {"item_id": str(item_id), "questions_bound": bound, "status": STATUS_APPROVED}

    async def split_item(self, item_id: uuid.UUID, reviewer_id: uuid.UUID) -> dict[str, Any]:
        """Resolve a group question-by-question instead of as a block.

        Needed when an old subtopic was broader than any single objective in the newer
        curriculum. Binding such a group to one objective would mis-target most of its
        questions — and unlike pre-existing mis-filing, that is damage the remap itself
        would introduce, because the new curriculum splits what the old one merged.

        Each question is judged on the skill it actually requires. Anything the model
        declines stays unbound and is reported, rather than being forced onto the
        group's majority objective.
        """
        item = await self._get_pending(item_id)
        if not item.candidates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This group has no candidate objectives to split across.",
            )

        rows = await self.db.execute(
            select(QuestionBank).where(
                QuestionBank.id.in_([uuid.UUID(q) for q in item.question_ids]),
                QuestionBank.learning_objective_id.is_(None),
            )
        )
        questions = list(rows.scalars().all())
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Every question in this group is already bound.",
            )

        # Candidates for a split must span the whole subject, not just the group's
        # shortlist. Old subtopics were not merely broad, they were mis-filed: of the
        # 103 questions under "Ratio and Proportion", 87 turned out to be number theory
        # (primes, factors, multiples). Offering only the group's three ratio
        # objectives leaves those permanently unbindable even though the new curriculum
        # has exact objectives for them.
        subject_objectives = await self._subject_objectives(item.subject_code)
        by_code = {c["canonical_code"]: c["objective_id"] for c in item.candidates}
        for objective in subject_objectives:
            by_code.setdefault(objective["canonical_code"], objective["objective_id"])

        # Snapshot every value the adjudicator needs BEFORE fanning out. Concurrent
        # tasks must not touch ORM instances: they share one AsyncSession, and any
        # attribute that needs refreshing would issue a query outside the greenlet
        # context and fail.
        payloads = [
            {
                "id": q.id,
                "question_text": q.question_text,
                "options": q.options if isinstance(q.options, list) else None,
            }
            for q in questions
        ]
        # Shortlist per question by embedding similarity across the subject, so the
        # model chooses between plausible objectives rather than the whole catalogue.
        shortlists = await self._shortlist_per_question(payloads, subject_objectives, item.candidates)
        semaphore = asyncio.Semaphore(_SPLIT_CONCURRENCY)

        async def decide(payload: dict[str, Any]) -> tuple[uuid.UUID, str | None]:
            async with semaphore:
                code = await adjudicate_question(
                    payload,
                    {
                        "subject_code": item.subject_code,
                        "grade_level": item.grade_level,
                        "old_learning_objective": item.source_learning_objective,
                        "candidates": shortlists[payload["id"]],
                    },
                )
                return cast("uuid.UUID", payload["id"]), code

        results = await asyncio.gather(*(decide(p) for p in payloads))

        per_objective: dict[str, list[uuid.UUID]] = {}
        undecided = 0
        for question_id, code in results:
            if code is None or code not in by_code:
                undecided += 1
                continue
            per_objective.setdefault(code, []).append(question_id)

        bound = 0
        for code, question_ids in per_objective.items():
            result = await self.db.execute(
                update(QuestionBank)
                .where(
                    QuestionBank.id.in_(question_ids),
                    QuestionBank.learning_objective_id.is_(None),
                )
                .values(learning_objective_id=uuid.UUID(by_code[code]))
            )
            bound += cast("CursorResult[Any]", result).rowcount or 0

        breakdown = ", ".join(f"{code}: {len(ids)}" for code, ids in sorted(per_objective.items()))
        item.status = STATUS_SPLIT
        item.resolved_by = reviewer_id
        item.resolved_at = datetime.now(UTC)
        item.admin_note = f"Split across {len(per_objective)} objectives — {breakdown}" + (
            f"; {undecided} left unbound for manual review" if undecided else ""
        )
        await self.db.commit()

        logger.info(
            "lo_review_item_split",
            item_id=str(item_id),
            source_code=item.source_code,
            questions_considered=len(questions),
            questions_bound=bound,
            objectives_used=len(per_objective),
            undecided=undecided,
            reviewer_id=str(reviewer_id),
        )
        return {
            "item_id": str(item_id),
            "questions_bound": bound,
            "objectives_used": len(per_objective),
            "undecided": undecided,
            "status": STATUS_SPLIT,
        }

    async def reject_item(
        self,
        item_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        admin_note: str | None = None,
    ) -> dict[str, Any]:
        """Close an item without binding anything.

        Used when no candidate assesses the same skill. The questions stay unbound and
        surface in the coverage report as a genuine gap — which is the honest outcome,
        and better than forcing them onto an approximate objective.
        """
        item = await self._get_pending(item_id)

        item.status = STATUS_REJECTED
        item.resolved_by = reviewer_id
        item.resolved_at = datetime.now(UTC)
        item.admin_note = admin_note
        await self.db.commit()

        logger.info(
            "lo_review_item_rejected",
            item_id=str(item_id),
            source_code=item.source_code,
            question_count=item.question_count,
            reviewer_id=str(reviewer_id),
        )
        return {"item_id": str(item_id), "questions_bound": 0, "status": STATUS_REJECTED}

    async def list_item_questions(self, item_id: uuid.UUID) -> dict[str, Any]:
        """Return every question in a group with the objective it is bound to.

        A split reports only a per-objective tally, which is a summary, not a review.
        This is what makes the individual assignments inspectable and correctable —
        without it the model's per-question decisions are unauditable.
        """
        item = await self.db.execute(
            select(LearningObjectiveReviewItem).where(LearningObjectiveReviewItem.id == item_id)
        )
        row = item.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review item {item_id} not found")

        result = await self.db.execute(
            select(QuestionBank, LearningObjective)
            .outerjoin(LearningObjective, LearningObjective.id == QuestionBank.learning_objective_id)
            .where(QuestionBank.id.in_([uuid.UUID(q) for q in row.question_ids]))
            # Unbound first: those are the ones still needing a human.
            .order_by(LearningObjective.canonical_code.nulls_first(), QuestionBank.question_text)
        )
        questions = [
            {
                "question_id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "difficulty_level": q.difficulty_level,
                "objective_id": str(lo.id) if lo else None,
                "objective_code": lo.canonical_code if lo else None,
                "objective_text": lo.learning_objective if lo else None,
            }
            for q, lo in result.all()
        ]
        return {
            "item_id": str(row.id),
            "source_name": row.source_name,
            "source_learning_objective": row.source_learning_objective,
            "total": len(questions),
            "unbound": sum(1 for q in questions if q["objective_id"] is None),
            "questions": questions,
        }

    async def rebind_question(
        self,
        question_id: uuid.UUID,
        objective_id: uuid.UUID | None,
        reviewer_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Move one question to a different objective, or unbind it entirely.

        Unlike the group actions this overwrites an existing binding — that is the
        point: it exists to correct a machine decision a human disagrees with.
        """
        result = await self.db.execute(select(QuestionBank).where(QuestionBank.id == question_id))
        question = result.scalar_one_or_none()
        if question is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {question_id} not found")

        if objective_id is not None:
            objective = await self.db.execute(select(LearningObjective).where(LearningObjective.id == objective_id))
            if objective.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Learning objective {objective_id} not found"
                )

        previous = question.learning_objective_id
        question.learning_objective_id = objective_id
        await self.db.commit()

        logger.info(
            "lo_review_question_rebound",
            question_id=str(question_id),
            previous_objective_id=str(previous) if previous else None,
            new_objective_id=str(objective_id) if objective_id else None,
            reviewer_id=str(reviewer_id),
        )
        return {"question_id": str(question_id), "objective_id": str(objective_id) if objective_id else None}

    async def search_objectives(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Free-text objective search, so a reviewer can pick outside the shortlist."""
        pattern = f"%{query.strip()}%"
        rows = await self.db.execute(
            select(LearningObjective)
            .where(
                LearningObjective.is_active.is_(True),
                # Bound parameters — never string-formatted into the SQL.
                (LearningObjective.learning_objective.ilike(pattern))
                | (LearningObjective.canonical_code.ilike(pattern))
                | (LearningObjective.name.ilike(pattern)),
            )
            .order_by(LearningObjective.canonical_code)
            .limit(limit)
        )
        return [
            {
                "objective_id": str(o.id),
                "canonical_code": o.canonical_code,
                "name": o.name,
                "learning_objective": o.learning_objective,
            }
            for o in rows.scalars().all()
        ]

    async def _subject_objectives(self, subject_code: str | None) -> list[dict[str, Any]]:
        """Active objectives placed somewhere in this subject, with their embeddings."""
        if not subject_code:
            return []
        rows = await self.db.execute(
            text(
                """
                SELECT DISTINCT lo.id::text AS objective_id, lo.canonical_code,
                                lo.learning_objective, lo.embedding
                FROM learning_objectives lo
                JOIN subtopic_objectives so ON so.learning_objective_id = lo.id
                JOIN subtopics sub          ON sub.id = so.subtopic_id
                JOIN curriculum_topics ct   ON ct.id = sub.curriculum_topic_id
                JOIN subjects s             ON s.id = ct.subject_id AND s.code = :subject
                WHERE lo.is_active AND lo.embedding IS NOT NULL
                """
            ),
            {"subject": subject_code},
        )
        return [dict(r) for r in rows.mappings()]

    async def _shortlist_per_question(
        self,
        payloads: list[dict[str, Any]],
        subject_objectives: list[dict[str, Any]],
        fallback: list[dict[str, Any]],
    ) -> dict[uuid.UUID, list[dict[str, Any]]]:
        """Pick the closest objectives for each question by embedding similarity.

        Falls back to the group's own candidates if embeddings are unavailable, so a
        provider outage degrades the shortlist rather than failing the split.
        """
        if not subject_objectives:
            return {p["id"]: fallback for p in payloads}

        try:
            vectors = await embed_all([p["question_text"] for p in payloads])
        except Exception as exc:
            logger.warning("split_shortlist_embedding_failed", error=str(exc))
            return {p["id"]: fallback for p in payloads}

        prepared = [(o, parse_vector(o["embedding"])) for o in subject_objectives]
        shortlists: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for payload, vector in zip(payloads, vectors, strict=True):
            scored = sorted(
                ((cosine_similarity(vector, emb), o) for o, emb in prepared if emb is not None),
                key=lambda pair: pair[0],
                reverse=True,
            )
            shortlists[payload["id"]] = [
                {
                    "objective_id": o["objective_id"],
                    "canonical_code": o["canonical_code"],
                    "learning_objective": o["learning_objective"],
                    "similarity": round(score, 4),
                }
                for score, o in scored[:_SPLIT_SHORTLIST_SIZE]
            ] or fallback
        return shortlists

    async def _get_pending(self, item_id: uuid.UUID) -> LearningObjectiveReviewItem:
        result = await self.db.execute(
            select(LearningObjectiveReviewItem).where(LearningObjectiveReviewItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review item {item_id} not found",
            )
        if item.status != STATUS_PENDING:
            # Two reviewers on the same queue must not both resolve one item.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Review item is already {item.status}",
            )
        return item

    @staticmethod
    def _serialise(item: LearningObjectiveReviewItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "item_type": item.item_type,
            "status": item.status,
            "source_code": item.source_code,
            "source_name": item.source_name,
            "source_learning_objective": item.source_learning_objective,
            "subject_code": item.subject_code,
            "grade_level": item.grade_level,
            "question_count": item.question_count,
            "candidates": item.candidates,
            "llm_suggested_code": item.llm_suggested_code,
            "llm_reason": item.llm_reason,
            "chosen_objective_id": str(item.chosen_objective_id) if item.chosen_objective_id else None,
            "admin_note": item.admin_note,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        }


async def upsert_review_item(
    db: AsyncSession,
    *,
    item_type: str,
    source_code: str,
    source_name: str | None,
    source_learning_objective: str,
    subject_code: str | None,
    grade_level: int | None,
    question_ids: list[str],
    candidates: list[dict[str, Any]],
    llm_suggested_code: str | None = None,
    llm_reason: str | None = None,
) -> bool:
    """Create or refresh a pending review item. Returns True if a row was written.

    Called by the remap scripts. Already-resolved items are left alone: re-running the
    pipeline must never reopen a decision an educator has already made.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO lo_review_items (
                id, item_type, status, source_code, source_name, source_learning_objective,
                subject_code, grade_level, question_count, candidates, question_ids,
                llm_suggested_code, llm_reason, created_at
            )
            VALUES (
                gen_random_uuid(), :item_type, 'PENDING', :source_code, :source_name, :source_lo,
                :subject_code, :grade_level, :question_count,
                CAST(:candidates AS jsonb), CAST(:question_ids AS jsonb),
                :llm_code, :llm_reason, now()
            )
            ON CONFLICT (item_type, source_code) DO UPDATE SET
                source_name               = EXCLUDED.source_name,
                source_learning_objective = EXCLUDED.source_learning_objective,
                question_count            = EXCLUDED.question_count,
                candidates                = EXCLUDED.candidates,
                question_ids              = EXCLUDED.question_ids,
                llm_suggested_code        = EXCLUDED.llm_suggested_code,
                llm_reason                = EXCLUDED.llm_reason,
                updated_at                = now()
            WHERE lo_review_items.status = 'PENDING'
            """
        ),
        {
            "item_type": item_type,
            "source_code": source_code,
            "source_name": source_name,
            "source_lo": source_learning_objective,
            "subject_code": subject_code,
            "grade_level": grade_level,
            "question_count": len(question_ids),
            "candidates": json.dumps(candidates),
            "question_ids": json.dumps(question_ids),
            "llm_code": llm_suggested_code,
            "llm_reason": llm_reason,
        },
    )
    return bool(cast("CursorResult[Any]", result).rowcount)


async def adjudicate_question(
    question: dict[str, Any],
    context: dict[str, Any],
) -> str | None:
    """Return the canonical_code this single question assesses, or None to decline.

    Every failure mode degrades to a decline. A wrong binding is silent — the question
    is served to students as evidence of a skill it does not test, and nothing
    downstream detects it — so an unparseable or out-of-range reply must never be
    turned into a guess.
    """
    candidates: list[dict[str, Any]] = context["candidates"]
    template = _jinja_env.get_template("lo_matching_question.jinja2")
    prompt = template.render(
        subject_code=context["subject_code"],
        grade_level=context["grade_level"],
        question_text=question["question_text"],
        options=question["options"],
        old_learning_objective=context["old_learning_objective"],
        candidates=candidates,
    )

    try:
        raw = await complete(
            "lo_matching",
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=120,
        )
    except Exception as exc:
        logger.warning("split_adjudication_failed", question_id=str(question["id"]), error=str(exc))
        return None

    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("split_adjudication_unparseable", question_id=str(question["id"]))
        return None

    choice = parsed.get("choice")
    if not isinstance(choice, int) or not 1 <= choice <= len(candidates):
        return None
    code = candidates[choice - 1].get("canonical_code")
    return str(code) if code else None
