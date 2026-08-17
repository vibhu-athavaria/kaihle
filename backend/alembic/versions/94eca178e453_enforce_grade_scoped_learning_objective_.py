"""enforce grade-scoped learning objective identity

Revision ID: 94eca178e453
Revises: 2a0f35d51c5c
Create Date: 2026-08-14 06:14:51.534645

ADR-003 T4. Makes (topic_id, grade_id, normalised_objective) the enforced identity of a
learning objective, so a question's grade is derivable from its objective alone and no
longer depends on subtopic_id surviving a curriculum remap.

RUN ORDER — this migration FAILS unless T1 and T3 have already run on this database:

    alembic upgrade 2a0f35d51c5c            <- stop here, not `upgrade head`
    python -m scripts.backfill_objective_grades --expected-null 12
    python -m scripts.split_spanning_objectives
    alembic upgrade head                    <- this migration

`alembic upgrade head` from 2a0f35d51c5c in one step will abort: the data steps in
between are what remove the NULLs. The pre-check below names the offending rows rather
than leaving an operator with Postgres's bare "column contains null values".

The data steps are deliberately NOT performed here. The split creates review-queue items
for questions whose grade cannot be inferred, which is application logic and belongs in a
script a human runs and reads the output of — not inside a migration.

Why the unique key is on normalised_objective and not canonical_code: two rows with the
same concept under different codes is the exact duplication ADR-003 exists to prevent, and
canonical_code cannot detect it. Grade is in the key because one objective text may
legitimately be taught at several grades; that is what T3's split produces, and the copies
share normalised_objective without colliding precisely because their grades differ.

Why normalised_objective is a stored column and not GENERATED: the normalisation folds
accents via NFKD, which Postgres can only approximate through unaccent(), and unaccent()
is not IMMUTABLE. Non-immutable functions are rejected in both generated-column
expressions and index expressions, so both alternatives fail at ALTER TABLE.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94eca178e453"
down_revision: str | Sequence[str] | None = "2a0f35d51c5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _abort_if_unresolved() -> None:
    """Fail with the offending rows named, before touching the schema.

    A read-only guard, not application logic: it runs the same query the operator would
    run by hand and puts the answer in the failure message. Without it the operator sees
    only "column grade_id contains null values" and has to go find out which.
    """
    connection = op.get_bind()

    for column, script in (
        ("grade_id", "scripts.backfill_objective_grades then scripts.split_spanning_objectives"),
        ("normalised_objective", "scripts.backfill_objective_grades"),
    ):
        rows = connection.execute(
            sa.text(f"SELECT canonical_code FROM learning_objectives WHERE {column} IS NULL ORDER BY canonical_code")  # noqa: S608
        ).scalars()
        offending = list(rows)
        if offending:
            sample = ", ".join(offending[:10]) + (" ..." if len(offending) > 10 else "")
            raise RuntimeError(
                f"{len(offending)} learning_objectives rows have {column} IS NULL, so it cannot be "
                f"made NOT NULL. Run `python -m {script}` first. Offending: {sample}"
            )

    duplicates = connection.execute(
        sa.text("""
            SELECT topic_id, grade_id, normalised_objective, count(*) AS n
            FROM learning_objectives
            GROUP BY 1, 2, 3
            HAVING count(*) > 1
        """)
    ).all()
    if duplicates:
        # Not something a script fixes — two rows claim the same concept at the same
        # grade, and choosing which survives is a curriculum judgement.
        raise RuntimeError(
            f"{len(duplicates)} (topic_id, grade_id, normalised_objective) triples are duplicated, "
            "so the unique constraint cannot be created. These need merging by hand — "
            "de-duplication is a curriculum decision, not a mechanical one."
        )


def upgrade() -> None:
    """Upgrade schema."""
    _abort_if_unresolved()

    op.alter_column("learning_objectives", "grade_id", nullable=False)
    op.alter_column("learning_objectives", "normalised_objective", nullable=False)
    op.create_unique_constraint(
        "uq_learning_objective_topic_grade_text",
        "learning_objectives",
        ["topic_id", "grade_id", "normalised_objective"],
    )


def downgrade() -> None:
    """Downgrade schema.

    Fully reversible: relaxing a constraint destroys no data. The rows keep their grade
    and their normalised text; they merely stop being required to have them.
    """
    op.drop_constraint("uq_learning_objective_topic_grade_text", "learning_objectives", type_="unique")
    op.alter_column("learning_objectives", "normalised_objective", nullable=True)
    op.alter_column("learning_objectives", "grade_id", nullable=True)
