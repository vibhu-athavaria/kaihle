"""Centralised email sending service backed by Jinja2 templates and Resend."""

from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent.parent / "emails"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
    undefined=StrictUndefined,  # raises on missing variables — no silent blanks
)


class EmailService:
    """Render Jinja2 email templates and send via Resend."""

    def render_template(self, template_name: str, ctx: dict[str, object]) -> str:
        """Render a template file with the given context. Raises if any variable is missing."""
        template = _env.get_template(template_name)
        return template.render(**ctx)

    async def send(self, *, to: str, subject: str, template: str, ctx: dict[str, object]) -> None:
        """Render template and send email via Resend. Logs and re-raises on failure.

        Callers must ensure `to` is a non-empty string before calling this method.
        """
        import resend

        from app.core.config import settings

        html = self.render_template(template, {**ctx, "subject": subject})

        resend.api_key = settings.resend_api_key
        try:
            resend.Emails.send(
                {
                    "from": settings.from_email,
                    "to": to,
                    "subject": subject,
                    "html": html,
                }
            )
            logger.info("email_sent", to=to, subject=subject, template=template)
        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to,
                subject=subject,
                template=template,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise
