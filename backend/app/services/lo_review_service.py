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
from sqlalchemy import ARRAY, Text, func, select, text, update
from sqlalchemy import cast as sa_cast
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.router import complete
from app.ai.similarity import cosine_similarity, embed_all, parse_vector
from app.models.curriculum import LearningObjective, LearningObjectiveReviewItem, QuestionBank

logger = structlog.get_logger()

ITEM_TYPE_QUESTION_REMAP = "QUESTION_REMAP"
ITEM_TYPE_REMAINDER = "QUESTION_REMAP_REMAINDER"
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
        unbound = await self._unbound_counts(items)

        payload = []
        for item in items:
            row = self._serialise(item)
            row["unbound_count"] = unbound.get(str(item.id), 0)
            payload.append(row)

        return {"total": int(total.scalar_one()), "items": payload}

    async def _unbound_counts(self, items: list[LearningObjectiveReviewItem]) -> dict[str, int]:
        """How many of each item's questions still have no objective.

        A SPLIT card is not self-evidently finished — the model declines on ambiguous
        questions — so the card must say how much work is left rather than making the
        reviewer open it to find out. One aggregate query for the whole page, never
        one per card.
        """
        wanted: dict[str, list[uuid.UUID]] = {
            str(item.id): [uuid.UUID(q) for q in item.question_ids] for item in items if item.question_ids
        }
        if not wanted:
            return {}

        every_id = {qid for ids in wanted.values() for qid in ids}
        rows = await self.db.execute(
            select(QuestionBank.id).where(QuestionBank.id.in_(every_id), QuestionBank.learning_objective_id.is_(None))
        )
        still_unbound = {r[0] for r in rows.all()}
        return {item_id: sum(1 for qid in ids if qid in still_unbound) for item_id, ids in wanted.items()}

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

        # Undecided questions must stay visible as outstanding work. Leaving them
        # only inside a SPLIT card made the Pending count understate the queue by 88
        # questions across two groups.
        undecided_ids = [str(qid) for qid, code in results if code is None or code not in by_code]
        if undecided_ids:
            await upsert_review_item(
                self.db,
                item_type=ITEM_TYPE_REMAINDER,
                source_code=f"{item.source_code}#REMAINDER",
                source_name=f"{item.source_name or item.source_code} — unresolved after split",
                source_learning_objective=item.source_learning_objective,
                subject_code=item.subject_code,
                grade_level=item.grade_level,
                question_ids=undecided_ids,
                # Deliberately no candidates: these questions are heterogeneous by
                # definition, so there is no single objective the group could bind to.
                candidates=[],
                llm_reason="Left unassigned during split — review each question individually.",
            )

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

    async def rebind_questions(
        self,
        question_ids: list[uuid.UUID],
        objective_id: uuid.UUID | None,
        reviewer_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Assign questions to an objective, or unbind them. Bulk by design.

        One-at-a-time is the wrong unit of work for what a split leaves behind: a run
        of "Calculate 123 x 15", "Calculate 23 x 4", "Calculate 246 x 37" plainly share
        an objective, and demanding a separate decision for each invites fatigue errors
        on precisely the least ambiguous cases.

        Unlike the group actions, this OVERWRITES existing bindings — correcting a
        machine decision a human disagrees with is the entire purpose.
        """
        if not question_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No questions selected.")

        if objective_id is not None:
            objective = await self.db.execute(select(LearningObjective).where(LearningObjective.id == objective_id))
            if objective.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Learning objective {objective_id} not found"
                )

        result = await self.db.execute(
            update(QuestionBank).where(QuestionBank.id.in_(question_ids)).values(learning_objective_id=objective_id)
        )
        updated = cast("CursorResult[Any]", result).rowcount or 0
        resolved = await self._resolve_completed_items(question_ids, reviewer_id)
        await self.db.commit()

        logger.info(
            "lo_review_questions_rebound",
            requested=len(question_ids),
            updated=updated,
            new_objective_id=str(objective_id) if objective_id else None,
            items_auto_resolved=len(resolved),
            reviewer_id=str(reviewer_id),
        )
        return {
            "updated": updated,
            "objective_id": str(objective_id) if objective_id else None,
            "items_resolved": resolved,
        }

    async def _resolve_completed_items(
        self, question_ids: list[uuid.UUID], reviewer_id: uuid.UUID
    ) -> list[dict[str, str]]:
        """Close any PENDING item whose last unbound question just got bound.

        Without this, an item worked question-by-question never leaves the queue: the
        reviewer binds all 54 of its questions and the card still reads PENDING, so the
        only way to tell finished work from outstanding work is to open every card.

        Deliberately one-way. Unbinding a question does NOT reopen a resolved item —
        a parent SPLIT group shares questions with its remainder item, so reopening
        would resurface a 103-question card because one question was unbound. Questions
        left unbound are already reported by the coverage validation, which is the right
        instrument for that.
        """
        touched = [str(qid) for qid in question_ids]
        candidates = await self.db.execute(
            select(LearningObjectiveReviewItem).where(
                LearningObjectiveReviewItem.status == STATUS_PENDING,
                # jsonb_exists_any: does question_ids share any element with `touched`?
                # Spelled as a function rather than the `?|` operator because the
                # right-hand side must bind as text[], and `?|` would coerce it to jsonb.
                func.jsonb_exists_any(
                    LearningObjectiveReviewItem.question_ids,
                    sa_cast(touched, ARRAY(Text)),
                ),
            )
        )
        resolved: list[dict[str, str]] = []
        for item in candidates.scalars().all():
            ids = [uuid.UUID(qid) for qid in item.question_ids]
            if not ids:
                continue
            rows = await self.db.execute(select(QuestionBank.learning_objective_id).where(QuestionBank.id.in_(ids)))
            bindings = [r[0] for r in rows.all()]
            if not bindings or any(b is None for b in bindings):
                continue

            # An item bound to a single objective was effectively an approval; one bound
            # across several was a split. Recording which keeps the audit trail honest.
            distinct = {str(b) for b in bindings}
            item.status = STATUS_APPROVED if len(distinct) == 1 else STATUS_SPLIT
            item.resolved_by = reviewer_id
            item.resolved_at = datetime.now(UTC)
            item.admin_note = f"Auto-resolved: all {len(ids)} questions assigned across {len(distinct)} objective(s)."
            resolved.append({"item_id": str(item.id), "status": item.status})
        return resolved

    async def search_objectives(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Find objectives by meaning, falling back to literal matching.

        The original implementation was a single ILIKE on the whole phrase, which
        required those exact words adjacent in the text. "addition subtraction"
        returned nothing even spelled correctly, because no objective contains that
        phrase — a reviewer describing a concept got silence.

        Reviewers describe concepts, not strings, so the primary path is embedding
        similarity over the same vectors the remap itself uses. Literal matching is
        kept as a supplement, since a canonical code typed verbatim should still work
        and needs no model call.
        """
        cleaned = query.strip()
        if not cleaned:
            return []

        results: dict[str, dict[str, Any]] = {}

        # Literal first: every term must appear somewhere, rather than the whole
        # phrase appearing verbatim.
        terms = [t for t in cleaned.split() if t]
        conditions = [
            (LearningObjective.learning_objective.ilike(f"%{t}%"))
            | (LearningObjective.canonical_code.ilike(f"%{t}%"))
            | (LearningObjective.name.ilike(f"%{t}%"))
            for t in terms
        ]
        rows = await self.db.execute(
            select(LearningObjective)
            .where(LearningObjective.is_active.is_(True), *conditions)
            .order_by(LearningObjective.canonical_code)
            .limit(limit)
        )
        for o in rows.scalars().all():
            results[str(o.id)] = {
                "objective_id": str(o.id),
                "canonical_code": o.canonical_code,
                "name": o.name,
                "learning_objective": o.learning_objective,
                "match": "literal",
            }

        if len(results) >= limit:
            return await self._with_placements(list(results.values())[:limit])

        # Semantic: rank the remaining slots by meaning.
        try:
            vector = (await embed_all([cleaned]))[0]
        except Exception as exc:
            logger.warning("objective_search_embedding_failed", error=str(exc))
            return await self._with_placements(list(results.values()))

        candidates = await self.db.execute(
            text(
                "SELECT id::text AS objective_id, canonical_code, name, learning_objective, embedding "
                "FROM learning_objectives WHERE is_active AND embedding IS NOT NULL"
            )
        )
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in candidates.mappings():
            emb = parse_vector(row["embedding"])
            if emb is None:
                continue
            scored.append(
                (
                    cosine_similarity(vector, emb),
                    {
                        "objective_id": row["objective_id"],
                        "canonical_code": row["canonical_code"],
                        "name": row["name"],
                        "learning_objective": row["learning_objective"],
                        "match": "semantic",
                    },
                )
            )
        scored.sort(key=lambda pair: pair[0], reverse=True)
        for _, item in scored:
            if len(results) >= limit:
                break
            results.setdefault(item["objective_id"], item)

        return await self._with_placements(list(results.values())[:limit])

    async def _with_placements(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach curriculum placement to each result. Every return path uses this."""
        placements = await self._placements_for([r["objective_id"] for r in results])
        for r in results:
            r["placements"] = placements.get(r["objective_id"], [])
        return results

    async def _placements_for(self, objective_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Where each objective sits in the curriculum: subject, grade, topic, subtopic.

        Objectives are deliberately grade-agnostic — grade is a property of placement,
        not of the concept, which is why one objective can be taught in several grades.
        But a reviewer deciding where a Grade 6 question belongs needs to see that
        context, otherwise the search returns a flat list of sentences with no way to
        tell a Grade 6 objective from a Grade 9 one.
        """
        if not objective_ids:
            return {}
        rows = await self.db.execute(
            text(
                """
                SELECT DISTINCT so.learning_objective_id::text AS objective_id,
                                s.code AS subject_code, g.level AS grade_level,
                                t.name AS topic_name, sub.name AS subtopic_name
                FROM subtopic_objectives so
                JOIN subtopics sub        ON sub.id = so.subtopic_id
                JOIN curriculum_topics ct ON ct.id = sub.curriculum_topic_id
                JOIN subjects s           ON s.id = ct.subject_id
                JOIN grades   g           ON g.id = ct.grade_id
                JOIN topics   t           ON t.id = ct.topic_id
                WHERE so.learning_objective_id = ANY(CAST(:ids AS uuid[]))
                ORDER BY 2, 3, 4, 5
                """
            ),
            {"ids": objective_ids},
        )
        placements: dict[str, list[dict[str, Any]]] = {}
        for row in rows.mappings():
            placements.setdefault(row["objective_id"], []).append(
                {
                    "subject_code": row["subject_code"],
                    "grade_level": row["grade_level"],
                    "topic_name": row["topic_name"],
                    "subtopic_name": row["subtopic_name"],
                }
            )
        return placements

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
