"""Platform-wide, admin-editable settings (singleton row).

Today it holds the production-evaluation controls (MLH-T18): a monthly USD budget, the
per-task allowlist, sampling bounds, and the privacy acknowledgements for tasks whose
prompts contain student-authored text.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSettings(Base):
    """The one platform-wide settings row. Always `id = 1`.

    NO `school_id` (CONSTITUTION Rule 2 deviation, MLH-T18 decision D13, approved by
    Vibhu 2026-10-11). These are settings of the Kaihle platform itself, edited only by
    KAIHLE_ADMIN; there is no per-school value to scope. Do not add a `school_id`.

    Singleton is enforced by the database: `id` is fixed to 1 by a CHECK constraint, so a
    second row cannot exist even under a concurrent first insert. The row is created
    lazily on the first update; until then the service returns the defaults below, which
    are fail-closed (budget 0, nothing enabled).
    """

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1, server_default="1")

    # Monthly cap on judge spend for production evaluation. 0 means "no production
    # evaluation may run" — an admin must raise it deliberately.
    eval_monthly_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0"
    )

    # Keys of router.TASK_MODEL_MAP that may be sampled. Empty = none.
    eval_enabled_tasks: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, default=list, server_default="{}"
    )

    eval_sample_size_per_task: Mapped[int] = mapped_column(Integer, nullable=False, default=50, server_default="50")
    eval_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")

    # Whether judge rubrics that are not CALIBRATED / HUMAN_VALIDATED also run (labelled
    # "indicative" in the UI).
    eval_include_indicative: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    # {task: {"acknowledged_by": "<user uuid>", "acknowledged_at": "<ISO-8601 UTC>"}} for
    # tasks that contain student text. Kept when a task is later disabled: it is the
    # record of who accepted the privacy risk and when. The actor is stored as a plain
    # string (not an FK) so the audit trail survives deletion of that user.
    eval_student_text_ack: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # NULL = the editor's account has since been deleted (SET NULL keeps the row).
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="chk_platform_settings_singleton"),
        CheckConstraint("eval_monthly_budget_usd >= 0", name="chk_platform_settings_budget_non_negative"),
        CheckConstraint("eval_sample_size_per_task BETWEEN 1 AND 200", name="chk_platform_settings_sample_size_range"),
        CheckConstraint("eval_window_days BETWEEN 1 AND 90", name="chk_platform_settings_window_range"),
    )
