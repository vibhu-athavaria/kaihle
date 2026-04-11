"""Unit tests for Content Curator — M3-1-T1."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.content_curator import (
    Resource,
    ResourceType,
    _deserialize_resources,
    _filter_active_videos,
    _normalise_view_count,
    curate_resources,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_content(videos: list[dict]) -> MagicMock:
    """Create a mock SubtopicContent with given videos JSONB."""
    c = MagicMock()
    c.videos = videos
    return c


def _mock_scalars_result(rows: list) -> MagicMock:
    """Build a mock db.execute() result where scalars().all() returns rows."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result.scalars.return_value = scalars_mock
    return result


def _mock_scalar_one_result(value) -> MagicMock:
    """Build a mock db.execute() result where scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# _normalise_view_count
# ---------------------------------------------------------------------------


class TestNormaliseViewCount:
    def test_zero(self):
        assert _normalise_view_count(0) == 0.0

    def test_negative(self):
        assert _normalise_view_count(-100) == 0.0

    def test_1k_views(self):
        # log10(1000) / 6 ≈ 0.50
        result = _normalise_view_count(1000)
        assert 0.49 < result < 0.51

    def test_10k_views(self):
        # log10(10000) / 6 ≈ 0.67
        result = _normalise_view_count(10_000)
        assert 0.66 < result < 0.68

    def test_100k_views(self):
        # log10(100000) / 6 ≈ 0.83
        result = _normalise_view_count(100_000)
        assert 0.82 < result < 0.84

    def test_1m_views(self):
        # log10(1000000) / 6 = 1.0
        assert _normalise_view_count(1_000_000) == 1.0

    def test_over_1m_capped(self):
        assert _normalise_view_count(10_000_000) == 1.0


# ---------------------------------------------------------------------------
# _filter_active_videos
#
# Filters out JSONB video entries marked status='stale' by the stale-link
# checker. Row-level approval is already enforced at query time; this
# helper only removes broken links from otherwise-approved rows.
# ---------------------------------------------------------------------------


class TestFilterActiveVideos:
    def test_empty_list_returns_empty(self):
        assert _filter_active_videos([]) == []

    def test_non_stale_videos_pass(self):
        """Videos with any status other than 'stale' are included."""
        videos = [
            {"url": "http://a", "status": "active"},
            {"url": "http://b", "status": "approved"},
        ]
        assert len(_filter_active_videos(videos)) == 2

    def test_stale_videos_excluded(self):
        """Videos with status='stale' are filtered out."""
        videos = [
            {"url": "http://a", "status": "active"},
            {"url": "http://b", "status": "stale"},
            {"url": "http://c", "status": "active"},
        ]
        result = _filter_active_videos(videos)
        assert len(result) == 2
        urls = [v["url"] for v in result]
        assert "http://b" not in urls

    def test_all_stale_returns_empty(self):
        videos = [
            {"url": "http://a", "status": "stale"},
            {"url": "http://b", "status": "stale"},
        ]
        assert _filter_active_videos(videos) == []

    def test_missing_status_passes(self):
        """Video entries with no status field are not filtered out."""
        videos = [{"url": "http://a"}]
        result = _filter_active_videos(videos)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _deserialize_resources
# ---------------------------------------------------------------------------


class TestDeserializeResources:
    def test_roundtrip(self):
        original = [
            Resource(
                url="http://youtube.com/v/1",
                title="Video 1",
                description="Channel A",
                resource_type=ResourceType.VIDEO,
                duration_seconds=300,
                source="youtube",
                thumbnail_url="http://thumb.com/1.jpg",
                final_score=0.85,
            )
        ]
        data = json.dumps([r.to_dict() for r in original])
        restored = _deserialize_resources(data)
        assert len(restored) == 1
        assert restored[0].url == "http://youtube.com/v/1"
        assert restored[0].title == "Video 1"
        assert restored[0].resource_type == ResourceType.VIDEO
        assert restored[0].duration_seconds == 300
        assert restored[0].final_score == 0.85

    def test_multiple_resources(self):
        data = json.dumps(
            [
                {
                    "url": "http://a",
                    "title": "A",
                    "description": "",
                    "resource_type": "video",
                    "duration_seconds": None,
                    "source": "youtube",
                    "thumbnail_url": None,
                    "final_score": 0.5,
                },
                {
                    "url": "http://b",
                    "title": "B",
                    "description": "",
                    "resource_type": "video",
                    "duration_seconds": 120,
                    "source": "youtube",
                    "thumbnail_url": None,
                    "final_score": 0.7,
                },
            ]
        )
        restored = _deserialize_resources(data)
        assert len(restored) == 2


# ---------------------------------------------------------------------------
# curate_resources — cache hit
# ---------------------------------------------------------------------------


class TestCurateResourcesCacheHit:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self):
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        cached_resources = [
            {
                "url": "http://cached",
                "title": "Cached Video",
                "description": "Desc",
                "resource_type": "video",
                "duration_seconds": 60,
                "source": "youtube",
                "thumbnail_url": None,
                "final_score": 0.9,
            }
        ]

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(cached_resources).encode()

        mock_db = AsyncMock()

        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )

        assert len(result) == 1
        assert result[0].url == "http://cached"
        mock_db.execute.assert_not_called()  # no DB hit


# ---------------------------------------------------------------------------
# curate_resources — cache miss
#
# curate_resources executes two DB queries:
#   1. SELECT StudentLearningProfile WHERE student_id = ... (profile)
#   2. SELECT SubtopicContent WHERE subtopic_id=... AND content_type=VIDEO
#      AND review_status=APPROVED AND is_active=TRUE AND is_archived=FALSE
#
# Profile query uses scalar_one_or_none(); content query uses scalars().all().
# ---------------------------------------------------------------------------


class TestCurateResourcesCacheMiss:
    @pytest.mark.asyncio
    async def test_no_content_returns_empty(self):
        """No approved content rows for this subtopic → empty result."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(None),  # profile query
                _mock_scalars_result([]),  # content query — no approved rows
            ]
        )

        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_all_stale_videos_returns_empty(self):
        """Approved content row exists but all videos are stale → empty result."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_content = make_content(
            [
                {"url": "http://a", "status": "stale", "view_count": 1000},
                {"url": "http://b", "status": "stale", "view_count": 500},
            ]
        )

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(None),  # profile
                _mock_scalars_result([mock_content]),  # content rows
            ]
        )

        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_active_videos_returned_sorted(self):
        """Active (non-stale) videos are returned sorted by view count descending."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_content = make_content(
            [
                {"url": "http://low", "status": "active", "view_count": 1_000, "title": "Low"},
                {"url": "http://high", "status": "active", "view_count": 1_000_000, "title": "High"},
                {"url": "http://mid", "status": "active", "view_count": 100_000, "title": "Mid"},
            ]
        )

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(None),
                _mock_scalars_result([mock_content]),
            ]
        )

        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )

        assert len(result) == 3
        # Sorted by final_score descending (high views first)
        assert result[0].url == "http://high"
        assert result[1].url == "http://mid"
        assert result[2].url == "http://low"

    @pytest.mark.asyncio
    async def test_modality_weighting_applied(self):
        """High visual modality score boosts video resources."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_content = make_content(
            [
                {"url": "http://v1", "status": "active", "view_count": 1000, "title": "V1"},
            ]
        )

        # Profile with high visual score
        mock_profile = MagicMock()
        mock_profile.modality_scores = {"visual": 0.8, "auditory": 0.3}

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(mock_profile),
                _mock_scalars_result([mock_content]),
            ]
        )

        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )

        assert len(result) == 1
        # Base score for 1000 views ≈ 0.50, with 1.3x visual multiplier = 0.65
        assert result[0].final_score is not None
        assert result[0].final_score > 0.5

    @pytest.mark.asyncio
    async def test_redis_failure_is_graceful(self):
        """Redis read failure falls back to DB lookup without raising."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis down")

        mock_content = make_content(
            [
                {"url": "http://a", "status": "active", "view_count": 1000, "title": "A"},
            ]
        )

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(None),
                _mock_scalars_result([mock_content]),
            ]
        )

        # Should not raise — graceful degradation
        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_redis_cache_write_failure_is_graceful(self):
        """Redis write failure after curating resources does not raise."""
        student_id = uuid4()
        subtopic_id = uuid4()
        school_id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.set.side_effect = Exception("Redis write failed")

        mock_content = make_content(
            [
                {"url": "http://a", "status": "active", "view_count": 1000, "title": "A"},
            ]
        )

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_one_result(None),
                _mock_scalars_result([mock_content]),
            ]
        )

        # Should not raise — graceful degradation
        result = await curate_resources(
            subtopic_id=subtopic_id,
            student_id=student_id,
            school_id=school_id,
            db=mock_db,
            redis_client=mock_redis,
        )
        assert len(result) == 1
