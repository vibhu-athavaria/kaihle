"""Unit tests for M3-0-T3 stale video link Celery job.

Tests the content_maintenance_tasks module covering:
- URL staleness detection (404, 403, 200, 405 cases)
- Network timeout behaviour (returns False, does not raise)
- Check interval logic (skip recently checked, check overdue)
- Video status filtering (skip rejected/stale)
- JSONB status update in videos array
- Rate limiting cap (MAX_URLS_PER_RUN)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.content_maintenance_tasks import (
    CHECK_INTERVAL_DAYS,
    MAX_URLS_PER_RUN,
    RATE_LIMIT_DELAY_S,
    REQUEST_TIMEOUT_S,
    _check_url,
    _run_stale_check,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_httpx_client():
    """Return a mock httpx.AsyncClient."""
    return AsyncMock()


@pytest.fixture
def sample_videos():
    """Return a sample videos JSONB array covering all status variants."""
    return [
        {
            "url": "https://youtube.com/watch?v=abc123",
            "title": "Video A",
            "status": "approved",
            "last_checked_at": None,
        },
        {
            "url": "https://youtube.com/watch?v=def456",
            "title": "Video B",
            "status": "pending",
            "last_checked_at": (datetime.now(UTC) - timedelta(days=8)).isoformat(),
        },
        {
            "url": "https://youtube.com/watch?v=ghi789",
            "title": "Video C",
            "status": "rejected",
            "last_checked_at": None,
        },
        {
            "url": "https://youtube.com/watch?v=jkl012",
            "title": "Video D",
            "status": "stale",
            "last_checked_at": None,
        },
    ]


# ---------------------------------------------------------------------------
# _check_url tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_url_when_404_then_returns_true(mock_httpx_client):
    """HTTP 404 response → URL is stale."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_httpx_client.head = AsyncMock(return_value=mock_response)

    result = await _check_url(mock_httpx_client, "https://youtube.com/watch?v=stale")

    assert result is True
    mock_httpx_client.head.assert_called_once()


@pytest.mark.asyncio
async def test_check_url_when_200_then_returns_false(mock_httpx_client):
    """HTTP 200 response → URL is reachable (not stale)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.head = AsyncMock(return_value=mock_response)

    result = await _check_url(mock_httpx_client, "https://youtube.com/watch?v=good")

    assert result is False


@pytest.mark.asyncio
async def test_check_url_when_403_then_returns_true(mock_httpx_client):
    """HTTP 403 Forbidden → URL is stale (content unavailable)."""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_httpx_client.head = AsyncMock(return_value=mock_response)

    result = await _check_url(mock_httpx_client, "https://youtube.com/watch?v=forbidden")

    assert result is True


@pytest.mark.asyncio
async def test_check_url_when_405_then_falls_back_to_get_and_returns_false(mock_httpx_client):
    """HTTP 405 on HEAD → falls back to GET, returns False (reachable)."""
    head_response = MagicMock()
    head_response.status_code = 405
    mock_httpx_client.head = AsyncMock(return_value=head_response)

    get_response = MagicMock()
    get_response.status_code = 200
    mock_httpx_client.get = AsyncMock(return_value=get_response)

    result = await _check_url(mock_httpx_client, "https://youtube.com/watch?v=ok")

    assert result is False
    mock_httpx_client.head.assert_called_once()
    mock_httpx_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_check_url_when_timeout_then_returns_false_and_logs_warning(mock_httpx_client):
    """Network timeout → returns False (don't mark stale on transient network issues)."""
    import httpx

    mock_httpx_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    # Implementation catches TimeoutException and returns False — does NOT raise
    result = await _check_url(mock_httpx_client, "https://youtube.com/watch?v=timeout")

    assert result is False


# ---------------------------------------------------------------------------
# _run_stale_check tests
#
# session.scalars() is awaited (async call) then iterated synchronously with
# `for content in rows:`. The mock return value must therefore be a plain
# sync-iterable list, NOT an AsyncMock with __aiter__.
# ---------------------------------------------------------------------------


def _make_stale_check_mocks(content_rows: list):
    """Build session / httpx mock context managers for _run_stale_check."""
    mock_session = AsyncMock()
    # scalars() is awaited — return a plain list for sync `for` iteration
    mock_session.scalars = AsyncMock(return_value=content_rows)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_session, mock_session_local


@pytest.mark.asyncio
async def test_stale_check_skips_videos_checked_recently(sample_videos):
    """Videos checked within CHECK_INTERVAL_DAYS are skipped."""
    # Override Video B's last_checked_at to 3 days ago (within 7-day window)
    recent_time = datetime.now(UTC) - timedelta(days=3)
    sample_videos[1]["last_checked_at"] = recent_time.isoformat()

    checked_urls: list[str] = []

    async def mock_head(url, **kwargs):
        checked_urls.append(url)
        response = MagicMock()
        response.status_code = 200
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([MagicMock(videos=sample_videos)])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    # Video A (abc123) should be checked — never checked before
    assert any("abc123" in url for url in checked_urls)
    # Video B (def456) was checked recently — should be skipped
    assert not any("def456" in url for url in checked_urls)


@pytest.mark.asyncio
async def test_stale_check_skips_rejected_videos(sample_videos):
    """Videos with status='rejected' are never rechecked."""
    checked_urls: list[str] = []

    async def mock_head(url, **kwargs):
        checked_urls.append(url)
        response = MagicMock()
        response.status_code = 200
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([MagicMock(videos=sample_videos)])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    # Video C (ghi789) is rejected — must never be rechecked
    assert not any("ghi789" in url for url in checked_urls)


@pytest.mark.asyncio
async def test_stale_check_skips_stale_videos(sample_videos):
    """Videos already marked 'stale' are not rechecked."""
    checked_urls: list[str] = []

    async def mock_head(url, **kwargs):
        checked_urls.append(url)
        response = MagicMock()
        response.status_code = 200
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([MagicMock(videos=sample_videos)])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    # Video D (jkl012) is already stale — must not be rechecked
    assert not any("jkl012" in url for url in checked_urls)


@pytest.mark.asyncio
async def test_stale_check_updates_last_checked_at_on_ok_url():
    """When URL is reachable, last_checked_at is updated but status stays the same."""
    video = {
        "url": "https://youtube.com/watch?v=good",
        "title": "Good Video",
        "status": "approved",
        "last_checked_at": None,
    }
    mock_content = MagicMock(videos=[video])

    async def mock_head(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([mock_content])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    # Status unchanged, last_checked_at populated
    assert video["status"] == "approved"
    assert video["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_stale_check_marks_stale_video_in_jsonb():
    """When URL returns 404, the video status is set to 'stale' in JSONB."""
    video = {
        "url": "https://youtube.com/watch?v=stale",
        "title": "Stale Video",
        "status": "approved",
        "last_checked_at": None,
    }
    mock_content = MagicMock(videos=[video])

    async def mock_head(url, **kwargs):
        response = MagicMock()
        response.status_code = 404
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([mock_content])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    assert video["status"] == "stale"
    assert video["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_stale_check_respects_max_urls_cap():
    """Processing stops after MAX_URLS_PER_RUN URLs have been checked."""
    many_videos = [
        {
            "url": f"https://youtube.com/watch?v=video{i}",
            "title": f"Video {i}",
            "status": "approved",
            "last_checked_at": None,
        }
        for i in range(MAX_URLS_PER_RUN + 50)
    ]

    checked_count = 0

    async def mock_head(url, **kwargs):
        nonlocal checked_count
        checked_count += 1
        response = MagicMock()
        response.status_code = 404
        return response

    mock_session, mock_session_local = _make_stale_check_mocks([MagicMock(videos=many_videos)])

    with (
        patch("app.tasks.content_maintenance_tasks.AsyncSessionLocal", mock_session_local),
        patch("app.tasks.content_maintenance_tasks.httpx.AsyncClient") as mock_client_cls,
        # Patch asyncio.sleep to avoid 500 * 0.5s = 250s test time
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.head = mock_head

        await _run_stale_check()

    assert checked_count == MAX_URLS_PER_RUN


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------


def test_constants_values():
    """Verify expected constant values from spec."""
    assert CHECK_INTERVAL_DAYS == 7
    assert REQUEST_TIMEOUT_S == 10
    assert RATE_LIMIT_DELAY_S == 0.5
    assert MAX_URLS_PER_RUN == 500
