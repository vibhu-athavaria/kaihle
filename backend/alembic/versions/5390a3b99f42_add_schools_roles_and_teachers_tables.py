"""Add schools, roles, and teachers tables

Revision ID: 5390a3b99f42
Revises: 2548e64cec42
Create Date: 2026-02-04 18:03:16.158287
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5390a3b99f42"
down_revision = "2548e64cec42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- roles -------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_index("ix_roles_id", "roles", ["id"])

    # ---- schools ----------------------------------------------
    op.create_table(
        "schools",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=500)),
        sa.Column("city", sa.String(length=100)),
        sa.Column("state", sa.String(length=100)),
        sa.Column("postal_code", sa.String(length=20)),
        sa.Column("country", sa.String(length=100)),
        sa.Column("phone", sa.String(length=20)),
        sa.Column("email", sa.String(length=255)),
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["users.id"],
            name="schools_admin_id_fkey",
        ),
    )

    op.create_index("ix_schools_id", "schools", ["id"])
    op.create_index("ix_schools_admin_id", "schools", ["admin_id"])

    # ---- teachers ---------------------------------------------
    op.create_table(
        "teachers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("qualifications", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("subjects_taught", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("experience_years", sa.Integer()),
        sa.Column("bio", sa.Text()),
        sa.Column("hire_date", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="teachers_school_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="teachers_user_id_fkey",
        ),
        sa.UniqueConstraint("user_id", name="uq_teachers_user_id"),
    )

    op.create_index("ix_teachers_id", "teachers", ["id"])
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"])
    op.create_index("ix_teachers_user_id", "teachers", ["user_id"])

    # ---- student_profiles.school_id ---------------------------
    op.add_column(
        "student_profiles",
        sa.Column("school_id", sa.UUID(), nullable=True),
    )

    op.create_index(
        "ix_student_profiles_school_id",
        "student_profiles",
        ["school_id"],
    )

    op.create_foreign_key(
        "student_profiles_school_id_fkey",
        "student_profiles",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # IMPORTANT:
    # Only undo what THIS revision created.

    # ---- student_profiles -------------------------------------
    op.drop_constraint(
        "student_profiles_school_id_fkey",
        "student_profiles",
        type_="foreignkey",
    )
    op.drop_index("ix_student_profiles_school_id", table_name="student_profiles")
    op.drop_column("student_profiles", "school_id")

    # ---- teachers ---------------------------------------------
    op.drop_index("ix_teachers_user_id", table_name="teachers")
    op.drop_index("ix_teachers_school_id", table_name="teachers")
    op.drop_index("ix_teachers_id", table_name="teachers")
    op.drop_table("teachers")

    # ---- schools ----------------------------------------------
    op.drop_index("ix_schools_admin_id", table_name="schools")
    op.drop_index("ix_schools_id", table_name="schools")
    op.drop_table("schools")

    # ---- roles ------------------------------------------------
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
