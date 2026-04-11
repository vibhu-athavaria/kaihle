"""Content Curation Engine — M3-1-T1.

Retrieves top 1–3 approved video resources for a student's gap subtopic,
ordered by popularity and learning-modality weighting.

Architecture (updated April 2026):
- No pgvector, no embeddings, no semantic search
- No Khan Academy source, no static index
- Resources come from subtopic_content.videos JSONB (KaihleAdmin-approved entries)
- Modality weighting boosts visual/auditory learners for video content
- Cache per (subtopic_id, student_id) for 24 hours
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

import redis.asyncio as redis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StudentLearningProfile
from app.models.subtopic_content import SubtopicContent

logger = structlog.get_logger()


class ResourceType(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    INTERACTIVE = "interactive"


@dataclass
class Resource:
    """Curation result — a single recommended learning resource."""

    url: str
    title: str
    description: str
    resource_type: ResourceType
    duration_seconds: int | None
    source: str
    thumbnail_url: str | None
    final_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type.value,
            "duration_seconds": self.duration_seconds,
            "source": self.source,
            "thumbnail_url": self.thumbnail_url,
            "final_score": self.final_score,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def curate_resources(
    subtopic_id: UUID,
    student_id: UUID,
    school_id: UUID,
    db: AsyncSession,
    redis_client: redis.Redis[Any] | None = None,
) -> list[Resource]:
    """Return top 1–3 approved video resources for a subtopic, ranked by modality score.

    Args:
        subtopic_id: UUID of the target Subtopic.
        student_id: UUID of the student (for learning profile lookup and cache key).
        school_id: UUID of the school (for future multi-tenant filtering).
        db: Async SQLAlchemy session.
        redis_client: Optional async Redis client for 24-hour caching.

    Returns:
        List of Resource objects (max 3), ordered by final score descending.
        Empty list if no approved content exists yet (graceful degradation).
    """
    cache_key = f"content:{subtopic_id}:{student_id}"

    # ---- 1. Cache check ----
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug("content_cache_hit", cache_key=cache_key)
                return _deserialize_resources(cached)
        except Exception as exc:
            logger.warning("redis_cache_read_failed", error=str(exc))

    # ---- 2. Load learning profile ----
    profile_result = await db.execute(
        select(StudentLearningProfile).where(StudentLearningProfile.student_id == student_id)
    )
    profile = profile_result.scalar_one_or_none()
    modality_scores = profile.modality_scores if profile else {}

    # ---- 3. Load approved video SubtopicContent rows ----
    # Filter at query level: content_type==video, review_status==approved, is_active, not archived
    from app.models.subtopic_content import ContentType, ReviewStatus  # noqa: PLC0415

    content_result = await db.execute(
        select(SubtopicContent)
        .where(SubtopicContent.subtopic_id == subtopic_id)
        .where(SubtopicContent.content_type == ContentType.VIDEO)
        .where(SubtopicContent.review_status == ReviewStatus.APPROVED)
        .where(SubtopicContent.is_active.is_(True))
        .where(SubtopicContent.is_archived.is_(False))
    )
    content_rows = content_result.scalars().all()

    if not content_rows:
        logger.warning(
            "subtopic_content_missing",
            subtopic_id=str(subtopic_id),
        )
        return []

    # ---- 4. Collect non-stale video entries from approved rows ----
    # videos JSONB entries have status "active"|"stale" (maintained by stale-link checker)
    all_videos: list[dict[str, Any]] = []
    for content in content_rows:
        all_videos.extend(_filter_active_videos(content.videos or []))

    if not all_videos:
        logger.info(
            "no_active_videos",
            subtopic_id=str(subtopic_id),
        )
        return []

    # ---- 5. Apply modality weighting ----
    scored = []
    for video in all_videos:
        base_score = _normalise_view_count(video.get("view_count", 0))
        multiplier = 1.0

        if modality_scores:
            # Visual and auditory learners both benefit from video
            if modality_scores.get("visual", 0) > 0.6:
                multiplier *= 1.3
            if modality_scores.get("auditory", 0) > 0.6:
                multiplier *= 1.2  # cumulative with visual multiplier

        final_score = base_score * multiplier
        video["final_score"] = final_score
        scored.append(video)

    scored.sort(key=lambda v: v["final_score"], reverse=True)
    top_videos = scored[:3]

    # ---- 6. Build Resource objects ----
    resources = [
        Resource(
            url=v["url"],
            title=v.get("title") or "Video",
            description=v.get("channel", ""),
            resource_type=ResourceType.VIDEO,
            duration_seconds=v.get("duration_seconds"),
            source=v.get("source", "youtube"),
            thumbnail_url=v.get("thumbnail_url"),
            final_score=v["final_score"],
        )
        for v in top_videos
    ]

    # ---- 7. Cache result ----
    if redis_client and resources:
        try:
            await redis_client.set(
                cache_key,
                json.dumps([r.to_dict() for r in resources]),
                ex=86400,  # 24 hours
            )
        except Exception as exc:
            logger.warning("redis_cache_write_failed", error=str(exc))

    logger.info(
        "resources_curated",
        subtopic_id=str(subtopic_id),
        student_id=str(student_id),
        count=len(resources),
    )
    return resources


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _filter_active_videos(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return video entries that are not marked stale by the stale-link checker.

    JSONB video entries have status 'active' or 'stale' (set by content_maintenance_tasks).
    Row-level approval is already filtered at the query level — this removes broken links.
    """
    return [v for v in videos if v.get("status") != "stale"]


def _normalise_view_count(view_count: int) -> float:
    """Normalise view count to 0.0–1.0 using log scale.

    1M views → ~1.0, 100K → ~0.83, 10K → ~0.67, 1K → ~0.50
    """
    if view_count <= 0:
        return 0.0
    return min(1.0, math.log10(max(1, view_count)) / 6.0)


def _deserialize_resources(data: str | bytes) -> list[Resource]:
    """Rehydrate a cached JSON string into Resource objects."""
    raw = json.loads(data) if isinstance(data, bytes) else json.loads(data)
    return [
        Resource(
            url=r["url"],
            title=r["title"],
            description=r["description"],
            resource_type=ResourceType(r["resource_type"]),
            duration_seconds=r.get("duration_seconds"),
            source=r["source"],
            thumbnail_url=r.get("thumbnail_url"),
            final_score=r.get("final_score"),
        )
        for r in raw
    ]
