"""fix_mini_course_chat_messages_created_at_default_drift

Revision ID: 49eb7ee197b3
Revises: a6ef5a235401
Create Date: 2026-09-10 00:35:41.008407

Both mini_course_chat_messages.created_at and mini_course_quiz_responses.created_at
were created with server_default="now()" (see f892502b0975), but at some point their
live column defaults were manually overridden to the literal
'2026-05-30 08:34:43.989769+00'::timestamptz — likely to produce reproducible demo/seed
timestamps — and never reverted. Every row relying on the default since then has
recorded that exact frozen value instead of its real insert time, which broke
chronological ordering (get_chat_history) for any conversation touched during that
window. Not caught by `alembic revision --autogenerate` because this project runs with
compare_server_default=False (see alembic/env.py), so a drifted server default is
invisible to the normal migration diff.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49eb7ee197b3"
down_revision: str | Sequence[str] | None = "a6ef5a235401"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DRIFTED_DEFAULT = "'2026-05-30 08:34:43.989769+00'::timestamp with time zone"


def upgrade() -> None:
    op.alter_column(
        "mini_course_chat_messages",
        "created_at",
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "mini_course_quiz_responses",
        "created_at",
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    # Restores the exact drifted value rather than a generic "now()" so downgrade is a
    # true inverse of upgrade — this migration's whole point is that these two states
    # are different and the difference matters.
    op.alter_column(
        "mini_course_chat_messages",
        "created_at",
        server_default=sa.text(_DRIFTED_DEFAULT),
    )
    op.alter_column(
        "mini_course_quiz_responses",
        "created_at",
        server_default=sa.text(_DRIFTED_DEFAULT),
    )
