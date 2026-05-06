"""Unit tests for EmailService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def email_service() -> EmailService:
    return EmailService()


class TestRenderTemplate:
    def test_render_template_when_valid_template_then_returns_html(
        self, email_service: EmailService, tmp_path: Path
    ) -> None:
        """render_template returns rendered HTML for a valid template and context."""
        # Use the real template directory — welcome_credentials is a known good template
        html = email_service.render_template(
            "welcome_credentials.html.jinja2",
            {
                "subject": "Test",
                "first_name": "Alice",
                "email": "alice@school.edu",
                "temp_password": "Temp1234!",
                "login_url": "http://localhost:3001/login",
                "school_name": "Test School",
            },
        )
        assert "Alice" in html
        assert "alice@school.edu" in html
        assert "Temp1234!" in html
        assert "http://localhost:3001/login" in html
        assert "Test School" in html

    def test_render_template_when_missing_variable_then_raises(self, email_service: EmailService) -> None:
        """render_template raises UndefinedError when a required variable is missing."""
        from jinja2 import UndefinedError

        with pytest.raises(UndefinedError):
            email_service.render_template(
                "welcome_credentials.html.jinja2",
                {"subject": "Test", "first_name": "Alice"},  # missing most ctx vars
            )

    def test_render_template_when_password_reset_template_then_returns_html(self, email_service: EmailService) -> None:
        """render_template returns HTML containing reset URL for password_reset template."""
        html = email_service.render_template(
            "password_reset.html.jinja2",
            {
                "subject": "Reset",
                "first_name": "Bob",
                "reset_url": "http://localhost:3001/reset-password?token=abc123",
            },
        )
        assert "Bob" in html
        assert "http://localhost:3001/reset-password?token=abc123" in html
        assert "24 hours" in html


class TestSend:
    @pytest.mark.asyncio
    async def test_send_when_resend_succeeds_then_logs_sent(self, email_service: EmailService) -> None:
        """send calls resend.Emails.send and logs email_sent on success."""
        mock_resend_send = MagicMock()
        with (
            patch("app.services.email_service.EmailService.render_template", return_value="<html>body</html>"),
            patch("resend.Emails.send", mock_resend_send),
            patch("app.services.email_service.logger") as mock_logger,
        ):
            await email_service.send(
                to="test@example.com",
                subject="Hello",
                template="password_reset.html.jinja2",
                ctx={"first_name": "X", "reset_url": "http://x.com"},
            )

        mock_resend_send.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "email_sent", to="test@example.com", subject="Hello", template="password_reset.html.jinja2"
        )

    @pytest.mark.asyncio
    async def test_send_when_resend_fails_then_logs_error_and_raises(self, email_service: EmailService) -> None:
        """send logs email_send_failed and re-raises when Resend throws."""
        with (
            patch("app.services.email_service.EmailService.render_template", return_value="<html/>"),
            patch("resend.Emails.send", side_effect=Exception("API down")),
            patch("app.services.email_service.logger") as mock_logger,
        ):
            with pytest.raises(Exception, match="API down"):
                await email_service.send(
                    to="test@example.com",
                    subject="Hello",
                    template="password_reset.html.jinja2",
                    ctx={},
                )

        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs["to"] == "test@example.com"
        assert call_kwargs["error_type"] == "Exception"
