"""add_interest_category_enum_type

Revision ID: 8fdf51b61aa5
Revises: 968bdc883d66
Create Date: 2026-05-15 18:04:28.906085

Converts interest_categories.name from free-text to a typed PostgreSQL enum.
Steps:
  1. Delete the two retired categories (Adventure & Exploration, Everyday Life).
  2. Rename surviving rows from human-readable labels to enum-key names.
  3. Create the interest_category_enum type.
  4. Cast the name column to the new enum type.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8fdf51b61aa5"
down_revision: str | Sequence[str] | None = "968bdc883d66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "interest_category_enum"
_ENUM_VALUES = ("sports_movement", "tech_gaming", "nature_animals", "arts_culture")

# Maps old human-readable label → new enum key
_RENAME_MAP = {
    "Sports & Fitness": "sports_movement",
    "Technology & Innovation": "tech_gaming",
    "Nature & Science": "nature_animals",
    "Music & Arts": "arts_culture",
}

# Reverse map for downgrade
_REVERSE_MAP = {v: k for k, v in _RENAME_MAP.items()}

_RETIRED = ("Adventure & Exploration", "Everyday Life")


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Delete retired categories
    conn.execute(
        sa.text("DELETE FROM interest_categories WHERE name = ANY(:names)"),
        {"names": list(_RETIRED)},
    )

    # 2. Rename surviving rows to enum-key names
    for old_name, new_name in _RENAME_MAP.items():
        conn.execute(
            sa.text("UPDATE interest_categories SET name = :new WHERE name = :old"),
            {"new": new_name, "old": old_name},
        )

    # 3. Create the enum type
    sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME).create(conn)

    # 4. Cast name column to enum type
    conn.execute(
        sa.text(f"ALTER TABLE interest_categories ALTER COLUMN name TYPE {_ENUM_NAME} USING name::text::{_ENUM_NAME}")
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Revert column back to text
    conn.execute(sa.text("ALTER TABLE interest_categories ALTER COLUMN name TYPE TEXT USING name::text"))

    # Drop the enum type
    sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME).drop(conn)

    # Rename rows back to human-readable labels
    for enum_key, old_name in _REVERSE_MAP.items():
        conn.execute(
            sa.text("UPDATE interest_categories SET name = :old WHERE name = :key"),
            {"old": old_name, "key": enum_key},
        )

    # Restore retired rows
    conn.execute(
        sa.text(
            "INSERT INTO interest_categories (id, name) VALUES "
            "(gen_random_uuid(), 'Adventure & Exploration'), "
            "(gen_random_uuid(), 'Everyday Life') "
            "ON CONFLICT (name) DO NOTHING"
        )
    )
