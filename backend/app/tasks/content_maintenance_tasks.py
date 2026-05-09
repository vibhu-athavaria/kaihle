"""Nightly background jobs for content maintenance.

M3-0-T3: Checks video URLs for staleness. Never called from request paths.
Runs every night at 02:00 via Celery beat.

Architecture: Iterates subtopic_content rows, checks each video URL in the
videos JSONB array that hasn't been checked in 7 days, marks broken URLs
as status='stale'. Rate-limited to avoid YouTube flagging.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from celery import Task, shared_task
from sqlalchemy import select

from app.core.database import CeleryAsyncSessionLocal
from app.models import SubtopicContent

logger = structlog.get_logger()

# Configuration constants
CHECK_INTERVAL_DAYS = 7  # only check URLs not checked in the last 7 days
REQUEST_TIMEOUT_S = 10  # per URL HEAD request timeout
RATE_LIMIT_DELAY_S = 0.5  # delay between requests to avoid rate limiting
MAX_URLS_PER_RUN = 500  # cap to keep job under ~5 minutes


class CheckStaleLinksTask(Task):
    """Celery Task subclass that emits a CRITICAL log when all retries are exhausted.

    Per CONSTITUTION Rule 18: tasks must emit a CRITICAL log on final retry exhaustion.
    """

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], einfo: Any
    ) -> None:
        """Called by Celery when all retries are exhausted.

        Emits a CRITICAL structured log event so the operations team is alerted.
        Per CONSTITUTION Rule 18.
        """
        logger.critical(
            "check_stale_video_links_permanently_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )


@shared_task(
    bind=True,
    base=CheckStaleLinksTask,
    max_retries=0,  # nightly job — if it fails, it runs again tomorrow
    ignore_result=True,
    name="tasks.check_stale_video_links",
)
def check_stale_video_links(self, *args: Any, **kwargs: Any) -> None:
    """Celery beat task — runs every night at 02:00.

    Iterates subtopic_content rows and checks each video URL that hasn't
    been checked in CHECK_INTERVAL_DAYS. Marks broken URLs as 'stale'.

    This task is NEVER called from request paths — it is a background
    maintenance job only.
    """
    logger.info("check_stale_video_links_started")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_stale_check())
    finally:
        loop.close()


async def _run_stale_check() -> None:
    """Core async logic for stale video link checking."""
    cutoff = datetime.now(UTC) - timedelta(days=CHECK_INTERVAL_DAYS)
    checked = 0
    stale_count = 0

    async with CeleryAsyncSessionLocal() as session:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "Kaihle-LinkChecker/1.0"},
        ) as client:
            # Fetch all subtopic_content rows that have videos
            rows = await session.scalars(
                select(SubtopicContent).where(
                    SubtopicContent.videos.isnot(None)  # only rows with videos
                )
            )

            for content in rows:
                if checked >= MAX_URLS_PER_RUN:
                    logger.info(
                        "stale_check_cap_reached",
                        max_urls=MAX_URLS_PER_RUN,
                    )
                    break

                videos = list(content.videos or [])
                updated = False

                for i, video in enumerate(videos):
                    if checked >= MAX_URLS_PER_RUN:
                        break  # cap applies within a single content row's videos too

                    # Skip rejected and stale — no point rechecking
                    video_status = video.get("status", "")
                    if video_status in ("rejected", "stale"):
                        continue

                    # Skip if checked recently
                    last_checked = video.get("last_checked_at")
                    if last_checked:
                        try:
                            last_dt = datetime.fromisoformat(last_checked)
                            # Make last_dt timezone-aware if it isn't
                            if last_dt.tzinfo is None:
                                last_dt = last_dt.replace(tzinfo=UTC)
                            if last_dt > cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass  # Invalid date format, recheck

                    # Perform HEAD request
                    url = video.get("url", "")
                    if not url:
                        continue

                    is_stale = await _check_url(client, url)
                    now_str = datetime.now(UTC).isoformat()
                    videos[i]["last_checked_at"] = now_str

                    if is_stale:
                        videos[i]["status"] = "stale"
                        stale_count += 1
                        logger.warning(
                            "video_link_stale",
                            subtopic_id=str(content.id),
                            url=url,
                            video_title=video.get("title", ""),
                        )
                        updated = True

                    checked += 1
                    await asyncio.sleep(RATE_LIMIT_DELAY_S)

                if updated:
                    content.videos = videos
                    await session.flush()  # Flush changes but don't commit yet

            await session.commit()

    logger.info(
        "stale_check_complete",
        urls_checked=checked,
        stale_found=stale_count,
    )


async def _check_url(client: httpx.AsyncClient, url: str) -> bool:
    """Check if a URL is reachable.

    Returns True if the URL is stale (broken/unavailable), False if reachable.
    Considers any non-2xx response (except 405 Method Not Allowed) as stale.
    405 is common for HEAD requests on some servers — treat as reachable.

    Network errors (timeout, connection error) return False — we don't mark
    URLs as stale on transient network issues.
    """
    try:
        response = await client.head(url)
        if response.status_code == 405:
            # HEAD not allowed — try GET with minimal bytes
            response = await client.get(url, headers={"Range": "bytes=0-0"})
        # Treat 2xx, 301, 302, 303, 307, 308 as reachable
        return response.status_code not in (200, 206, 301, 302, 303, 307, 308)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        logger.warning("url_check_error", url=url, error=str(exc))
        return False  # Network error ≠ stale — don't mark on network issues
