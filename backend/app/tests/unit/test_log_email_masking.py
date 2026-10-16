"""Tests that email addresses are masked before they reach log calls (privacy fix T19c)."""

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import mask_email
from app.models.user import UserRole
from app.schemas.school import SchoolCreate
from app.schemas.user import UserInvite
from app.services.email_service import EmailService
from app.services.school_service import SchoolService
from app.services.user_service import UserService
from app.tasks.mini_course_tasks import send_mini_course_ready_email
from app.tasks.question_review_tasks import _send_review_notification_async

RAW = "secret.person@example.com"


def _logged_text(mock_logger: MagicMock) -> str:
    """Flatten every call made on the patched logger into one string."""
    return repr(mock_logger.mock_calls)


class TestMaskEmail:
    def test_mask_email_when_normal_address_then_keeps_first_char_and_domain(self) -> None:
        assert mask_email("alice@school.edu") == "a***@school.edu"

    def test_mask_email_when_single_char_local_part_then_still_masked(self) -> None:
        assert mask_email("a@x.com") == "a***@x.com"

    def test_mask_email_when_no_at_sign_then_fully_masked(self) -> None:
        assert mask_email("not-an-email") == "***"

    def test_mask_email_when_empty_then_fully_masked(self) -> None:
        assert mask_email("") == "***"

    def test_mask_email_when_none_then_fully_masked(self) -> None:
        assert mask_email(None) == "***"

    def test_mask_email_when_empty_local_part_then_fully_masked(self) -> None:
        assert mask_email("@example.com") == "***"

    def test_mask_email_when_multiple_at_signs_then_uses_last_as_domain_separator(self) -> None:
        assert mask_email("a@b@example.com") == "a***@example.com"

    def test_mask_email_when_called_twice_then_deterministic(self) -> None:
        assert mask_email(RAW) == mask_email(RAW)

    def test_mask_email_when_masked_then_raw_address_not_in_output(self) -> None:
        assert "secret.person" not in mask_email(RAW)


class TestEmailServiceLogsMasked:
    @pytest.mark.asyncio
    async def test_send_when_success_then_log_does_not_contain_raw_address(self) -> None:
        with (
            patch("app.services.email_service.EmailService.render_template", return_value="<html/>"),
            patch("resend.Emails.send", MagicMock()),
            patch("app.services.email_service.logger") as mock_logger,
        ):
            await EmailService().send(to=RAW, subject="Hi", template="t.html", ctx={})

        assert RAW not in _logged_text(mock_logger)
        assert mock_logger.info.call_args[1]["to"] == mask_email(RAW)

    @pytest.mark.asyncio
    async def test_send_when_failure_then_log_does_not_contain_raw_address(self) -> None:
        with (
            patch("app.services.email_service.EmailService.render_template", return_value="<html/>"),
            patch("resend.Emails.send", side_effect=Exception("API down")),
            patch("app.services.email_service.logger") as mock_logger,
        ):
            with pytest.raises(Exception, match="API down"):
                await EmailService().send(to=RAW, subject="Hi", template="t.html", ctx={})

        assert RAW not in _logged_text(mock_logger)
        assert mock_logger.error.call_args[1]["to"] == mask_email(RAW)


class TestUserServiceLogsMasked:
    @pytest.mark.asyncio
    async def test_invite_user_when_valid_then_log_does_not_contain_raw_address(self) -> None:
        db = MagicMock(spec=AsyncSession)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.scalar = AsyncMock(return_value=None)
        data = UserInvite(email=RAW, role=UserRole.TEACHER, first_name="J", last_name="D", subjects=["Mathematics"])

        with (
            patch("app.services.user_service.create_magic_link_token", return_value="tok"),
            patch("app.services.user_service.hash_token", return_value="h"),
            patch("app.services.user_service.store_magic_link_token", return_value=MagicMock()),
            patch("app.services.user_service.UserService._send_welcome_email"),
            patch("app.services.user_service.logger") as mock_logger,
        ):
            await UserService(db).invite_user(uuid.uuid4(), data, "https://app.kaihle.com")

        assert RAW not in _logged_text(mock_logger)
        invited = [c for c in mock_logger.info.call_args_list if c.args[0] == "user_invited"]
        assert invited[0].kwargs["email"] == mask_email(RAW)


class TestSchoolServiceLogsMasked:
    @pytest.mark.asyncio
    async def test_create_school_when_valid_then_log_does_not_contain_raw_address(self) -> None:
        db = MagicMock(spec=AsyncSession)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.scalar = AsyncMock(return_value=None)
        data = SchoolCreate(
            name="S",
            slug="s",
            country="Indonesia",
            timezone="Asia/Jakarta",
            admin_email=RAW,
            admin_first_name="A",
            admin_last_name="B",
            admin_password="password123",
        )

        with patch("app.services.school_service.logger") as mock_logger:
            await SchoolService(db).create_school(data)

        assert RAW not in _logged_text(mock_logger)
        assert mock_logger.info.call_args[1]["admin_email"] == mask_email(RAW)


class TestMiniCourseTaskLogsMasked:
    def test_send_mini_course_ready_email_when_sent_then_log_does_not_contain_raw_address(self) -> None:
        with (
            patch("app.tasks.mini_course_tasks.resend.Emails.send"),
            patch("app.tasks.mini_course_tasks.logger") as mock_logger,
        ):
            send_mini_course_ready_email(RAW, "Fractions")

        assert RAW not in _logged_text(mock_logger)
        assert mock_logger.info.call_args[1]["teacher_email"] == mask_email(RAW)


class TestQuestionReviewTaskLogsMasked:
    @pytest.mark.asyncio
    async def test_send_review_notification_when_send_fails_then_log_does_not_contain_raw_address(self) -> None:
        db = MagicMock()
        db.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[SimpleNamespace(email=RAW, first_name="Ad")]))
        )
        session_cm: Any = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=db)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.database.AsyncSessionLocal", return_value=session_cm),
            patch("app.services.email_service.EmailService.send", AsyncMock(side_effect=RuntimeError("boom"))),
            patch("app.tasks.question_review_tasks.logger") as mock_logger,
        ):
            await _send_review_notification_async("rid", "TEACHER_QUESTION", "uid")

        assert RAW not in _logged_text(mock_logger)
        assert mock_logger.error.call_args[1]["to"] == mask_email(RAW)
