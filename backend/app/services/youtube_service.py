"""YouTube video search service.

Shared by seed_subtopic_content.py and the subtopic-content API refresh endpoint.
Searches YouTube for educational video candidates for a given subtopic.
"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

YOUTUBE_CANDIDATES_PER_REGION = 10
YOUTUBE_TOP_N = 3
YOUTUBE_REGIONS = ["US", "GB", "AU"]
YOUTUBE_ALLOWED_CHANNEL_COUNTRIES = {"US", "GB", "AU", "CA", "NZ"}


def _iso8601_duration_to_seconds(duration: str) -> int:
    """Convert ISO 8601 duration (PT4M13S) to total seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def _search_region(yt: Any, query: str, region: str) -> list[str]:
    """Return video IDs from a single region search (recently uploaded, medium duration)."""
    try:
        resp = (
            yt.search()
            .list(
                q=query,
                part="id",
                type="video",
                videoDuration="medium",
                order="date",
                maxResults=YOUTUBE_CANDIDATES_PER_REGION,
                regionCode=region,
                relevanceLanguage="en",
                safeSearch="strict",
            )
            .execute()
        )
        return [item["id"]["videoId"] for item in resp.get("items", [])]
    except Exception as e:
        log.warning("youtube_search region=%s failed: %s", region, e)
        return []


def search_youtube_videos(
    subtopic: dict[str, Any],
    yt_client: Any = None,
    api_key: str | None = None,
    exclude_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Search YouTube across US/GB/AU, rank by engagement, return top YOUTUBE_TOP_N.

    Args:
        subtopic: dict with keys name, _strand_id (subject), grade_level
        yt_client: pre-built googleapiclient resource (reused across calls for efficiency)
        api_key: YouTube Data API key (used when yt_client is not provided)
        exclude_urls: set of already-known video URLs to skip (dedup on refresh)

    Steps:
      1. search.list × 3 regions — collect up to 30 candidate IDs (deduplicated)
      2. videos.list — fetch statistics + contentDetails in one batch call
      3. channels.list — fetch channel countries in one batch call
      4. Filter: drop non-allowed channel countries, drop out-of-range durations,
         rank by likes + 0.1×views, return top YOUTUBE_TOP_N
    """
    try:
        from googleapiclient.discovery import build as yt_build  # type: ignore[import-untyped]
    except ImportError:
        log.error("google-api-python-client is not installed")
        return []

    if not api_key and yt_client is None:
        log.warning("no YouTube API key or client provided — skipping search for %s", subtopic.get("name"))
        return []

    name = subtopic.get("name", "")
    subject = subtopic.get("_strand_id", "Mathematics")
    grade = subtopic.get("grade_level", "Grade 8")
    query = f"{name} {subject} {grade} explained tutorial"

    exclude = exclude_urls or set()

    try:
        yt = yt_client or yt_build("youtube", "v3", developerKey=api_key, cache_discovery=False)

        seen: set[str] = set()
        video_ids: list[str] = []
        for region in YOUTUBE_REGIONS:
            for vid_id in _search_region(yt, query, region):
                if vid_id not in seen:
                    seen.add(vid_id)
                    video_ids.append(vid_id)

        if not video_ids:
            log.info("youtube_search | no results | subtopic=%s | query=%s", name, query)
            return []

        stats_resp = (
            yt.videos()
            .list(
                id=",".join(video_ids),
                part="id,snippet,statistics,contentDetails",
            )
            .execute()
        )

        channel_ids = list({item["snippet"]["channelId"] for item in stats_resp.get("items", [])})
        channel_country: dict[str, str | None] = {}
        if channel_ids:
            ch_resp = (
                yt.channels()
                .list(
                    id=",".join(channel_ids),
                    part="id,snippet",
                )
                .execute()
            )
            for ch in ch_resp.get("items", []):
                channel_country[ch["id"]] = ch.get("snippet", {}).get("country") or None

        candidates = []
        dropped_country: list[str] = []
        dropped_duration: list[str] = []
        for item in stats_resp.get("items", []):
            vid_id = item["id"]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            title = snippet.get("title", "")

            video_url = f"https://www.youtube.com/watch?v={vid_id}"
            if video_url in exclude:
                continue

            ch_country = channel_country.get(snippet.get("channelId", ""))
            if ch_country is not None and ch_country not in YOUTUBE_ALLOWED_CHANNEL_COUNTRIES:
                dropped_country.append(f"{title!r} (channel_country={ch_country})")
                continue

            likes = int(stats.get("likeCount", 0))
            views = int(stats.get("viewCount", 0))
            duration_s = _iso8601_duration_to_seconds(details.get("duration", ""))
            if not (60 <= duration_s <= 1200):
                dropped_duration.append(f"{title!r} ({duration_s}s)")
                continue

            score = likes + 0.1 * views
            candidates.append(
                {
                    "video_url": video_url,
                    "video_provider": "youtube",
                    "video_duration_seconds": duration_s,
                    "video_thumbnail_url": f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg",
                    "title": title,
                    "_score": score,
                }
            )

        if dropped_country:
            log.info("youtube_filter | dropped by country (%d): %s", len(dropped_country), ", ".join(dropped_country))
        if dropped_duration:
            log.info(
                "youtube_filter | dropped by duration (%d): %s", len(dropped_duration), ", ".join(dropped_duration)
            )

        candidates.sort(key=lambda x: x["_score"], reverse=True)
        top = candidates[:YOUTUBE_TOP_N]
        for v in top:
            del v["_score"]

        log.info(
            "youtube_search | subtopic=%s | pool=%d | after_filter=%d | selected=%d",
            name,
            len(video_ids),
            len(candidates),
            len(top),
        )
        return top

    except Exception as e:
        log.error("YouTube API error | subtopic=%s | error=%s", name, e)
        return []
