# M3-0-T3 — Stale Video Link Celery Job
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-0 — Content Infrastructure
**Task:** T3
**Executor:** Coding agent
**Depends on:** M3-0-T1 (subtopic_content table populated), M0-1-T2 (Celery infra)
**Blocks:** Nothing (background maintenance job)

> **This is a background maintenance task, not a user-facing feature.**
> It must never be called synchronously during request handling.
> Do not add it to any request path.

---

## User Story

As Kaihle Admin, I want stale or deleted YouTube video links to be automatically
detected and flagged so that students never receive a broken video link in their
study packs.

---

## Context

YouTube videos can become unavailable at any time — deleted, made private,
or age-restricted. Videos in `subtopic_content.videos` JSONB array that were
approved may become stale without warning.

This job runs nightly, checks every video URL via an HTTP HEAD request, and marks
any broken URLs as `status = 'stale'`. KaihleAdmin is notified so they can
approve a replacement from the remaining candidates or add a new one.

The job must:
- Run at low priority (nightly, off-peak hours)
- Never block lesson plan generation or study plan creation
- Check only approved and pending videos (skip already-rejected and stale)
- Rate-limit HEAD requests to avoid YouTube flagging the server

---

## Files to Create / Modify

```
CREATE  backend/app/tasks/content_maintenance_tasks.py
MODIFY  backend/app/tasks/celery_app.py   ← add beat schedule entry
CREATE  backend/tests/unit/test_stale_link_job.py
```

---

## Implementation

### `content_maintenance_tasks.py`

```python
"""
Nightly background jobs for content maintenance.
Checks video URLs for staleness. Never called from request paths.
"""
import asyncio
import httpx
import structlog
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy import select, update
from app.core.database import get_async_session

logger = structlog.get_logger()

CHECK_INTERVAL_DAYS = 7     # only check URLs not checked in the last 7 days
REQUEST_TIMEOUT_S   = 10    # per URL HEAD request timeout
RATE_LIMIT_DELAY_S  = 0.5   # delay between requests to avoid rate limiting
MAX_URLS_PER_RUN    = 500   # cap to keep job under ~5 minutes


@shared_task(
    name="tasks.check_stale_video_links",
    max_retries=0,    # nightly job — if it fails, it runs again tomorrow
    ignore_result=True,
)
def check_stale_video_links() -> None:
    """
    Celery beat task — runs every night at 02:00.
    Iterates subtopic_content rows and checks each video URL that hasn't
    been checked in CHECK_INTERVAL_DAYS. Marks broken URLs as 'stale'.
    """
    # Use new_event_loop — NOT asyncio.run() — per CONSTITUTION Celery pattern.
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_stale_check())
    finally:
        loop.close()


async def _run_stale_check() -> None:
    cutoff = datetime.utcnow() - timedelta(days=CHECK_INTERVAL_DAYS)
    checked = 0
    stale_count = 0

    async with get_async_session() as session:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "Kaihle-LinkChecker/1.0"},
        ) as client:
            # Fetch all subtopic_content rows that have videos
            rows = await session.scalars(
                select(SubtopicContent).where(
                    SubtopicContent.videos != cast("[]", JSONB)
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
                    # Skip rejected and stale — no point rechecking
                    if video.get("status") in ("rejected", "stale"):
                        continue

                    # Skip if checked recently
                    last_checked = video.get("last_checked_at")
                    if last_checked:
                        last_dt = datetime.fromisoformat(last_checked)
                        if last_dt > cutoff:
                            continue

                    # Perform HEAD request
                    url = video.get("url", "")
                    if not url:
                        continue

                    is_stale = await _check_url(client, url)
                    now_str = datetime.utcnow().isoformat()
                    videos[i]["last_checked_at"] = now_str

                    if is_stale:
                        videos[i]["status"] = "stale"
                        stale_count += 1
                        logger.warning(
                            "video_link_stale",
                            subtopic_id=str(content.subtopic_id),
                            url=url,
                            video_title=video.get("title", ""),
                        )
                        updated = True

                    checked += 1
                    await asyncio.sleep(RATE_LIMIT_DELAY_S)

                if updated:
                    content.videos = videos
                    content.updated_at = datetime.utcnow()

            await session.commit()

    logger.info(
        "stale_check_complete",
        urls_checked=checked,
        stale_found=stale_count,
    )


async def _check_url(client: httpx.AsyncClient, url: str) -> bool:
    """
    Returns True if the URL is stale (broken/unavailable), False if reachable.
    Considers any non-2xx response (except 405 Method Not Allowed) as stale.
    405 is common for HEAD requests on some servers — treat as reachable.
    """
    try:
        response = await client.head(url)
        if response.status_code == 405:
            # HEAD not allowed — try GET with minimal bytes
            response = await client.get(url, headers={"Range": "bytes=0-0"})
        return response.status_code not in (200, 206, 301, 302, 303, 307, 308)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        logger.warning("url_check_error", url=url, error=str(exc))
        return False   # Network error ≠ stale — don't mark as stale on network issues
```

### Beat schedule entry in `celery_app.py`

```python
app.conf.beat_schedule = {
    # existing entries ...
    "generate-weekly-lesson-plans": { ... },   # Monday 06:00

    # new entry:
    "check-stale-video-links": {
        "task": "tasks.check_stale_video_links",
        "schedule": crontab(hour=2, minute=0),   # every day at 02:00
    },
}
```

---

## Staleness Notification

After the job completes, if `stale_count > 0`, insert a notification record for
KaihleAdmin to pick up in their video review queue. Use a simple approach — add a
`stale_video_count` field to the next `GET /subtopic-content/review-queue` response
so the sidebar badge includes stale videos alongside pending ones.

No separate notification table needed for MVP. The review queue badge already shows
KaihleAdmin what needs attention.

The `VideoReviewQueue.tsx` (M3-0-T2a) query should include `status = 'stale'` in
its badge count so stale videos surface automatically.

---

## Acceptance Criteria

- [ ] Beat task fires every day at 02:00 (unit test with frozen clock)
- [ ] URLs not checked in last 7 days are checked; recently checked are skipped
- [ ] HTTP 404 response → video marked `status = 'stale'`
- [ ] HTTP 403 response → video marked `status = 'stale'`
- [ ] HTTP 200 response → video status unchanged, `last_checked_at` updated
- [ ] HTTP 405 response → falls back to GET, treats as reachable
- [ ] Network timeout → URL not marked stale (logged at WARNING)
- [ ] Already-rejected videos skipped (not rechecked)
- [ ] Already-stale videos skipped (not rechecked)
- [ ] Approved videos are checked (approval does not exempt from freshness checks)
- [ ] `MAX_URLS_PER_RUN` cap prevents unbounded runtime
- [ ] Rate limit delay applied between requests (0.5s)
- [ ] Job logs `stale_check_complete` with counts on finish
- [ ] Task failure on one URL does not stop processing remaining URLs
- [ ] CRITICAL log emitted on final retry exhaustion (per CONSTITUTION Rule 18)
- [ ] Task is NEVER called from a request handler

---

## Tests to Write

```python
# backend/tests/unit/test_stale_link_job.py

def test_check_url_when_404_then_returns_true()
def test_check_url_when_200_then_returns_false()
def test_check_url_when_403_then_returns_true()
def test_check_url_when_405_then_falls_back_to_get_and_returns_false()
def test_check_url_when_timeout_then_returns_false_and_logs_warning()
def test_stale_check_when_video_checked_recently_then_skipped()
def test_stale_check_when_video_overdue_then_checked()
def test_stale_check_when_rejected_status_then_always_skipped()
def test_stale_check_when_stale_status_then_always_skipped()
def test_stale_check_when_url_is_stale_then_status_updated_in_jsonb()
def test_stale_check_when_url_ok_then_last_checked_at_updated()
def test_stale_check_when_cap_reached_then_stops_at_max_urls()
def test_rate_limit_delay_applied_between_requests()
```

---

## Do NOT Touch

- Any request-path code — this task is background only
- `subtopic_content.approved_explanation` — not the concern of this task
- `subtopic_content.explanation_review_status` — not the concern of this task
- `curriculum_chunks` — never read or write

---

*Task M3-0-T3 · Kramer (Technical Lead) · April 2026*
