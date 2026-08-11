"""add IMPERSONATION auth_token_type

Kaihle Admin can now open a session as another user for support. The handoff link
that carries that grant across an origin boundary is stored in auth_tokens like
every other credential we issue, so it needs its own type value — reusing
MAGIC_LINK would make impersonation grants indistinguishable from password-setup
links in both queries and the audit trail.

Hand-written deliberately, as the one documented exception to CONSTITUTION Rule 9:
Alembic --autogenerate does not detect new values on an existing PostgreSQL enum
and produces an empty migration for this change.

Revision ID: b7c41f9d2ae8
Revises: e0203f141a86
Create Date: 2026-08-11

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c41f9d2ae8"
down_revision: str | Sequence[str] | None = "e0203f141a86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add IMPERSONATION to the auth_token_type enum.

    Runs in an autocommit block: ALTER TYPE ... ADD VALUE cannot be followed by
    use of the new value inside the same transaction. IF NOT EXISTS keeps this
    idempotent on re-run.
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE auth_token_type ADD VALUE IF NOT EXISTS 'IMPERSONATION'")


def downgrade() -> None:
    """No-op.

    PostgreSQL cannot remove a value from an enum type. Reversing this would mean
    recreating auth_token_type and rewriting the column, which risks live tokens
    for a value that is harmless to leave in place. Any IMPERSONATION rows expire
    within a minute of being issued and are purged by the nightly token cleanup.
    """
