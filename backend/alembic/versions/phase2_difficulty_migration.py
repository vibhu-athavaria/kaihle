"""Phase 2: Migrate difficulty from Float/Enum to Integer 1-5

Revision ID: phase2_difficulty
Revises: 52a620c3043a
Create Date: 2026-02-21

This migration standardises all difficulty values to Integer 1-5 scale:
- question_bank.difficulty_level: Float (0.0-1.0) -> Integer (1-5)
- assessments.difficulty_level: Enum (EASY/MEDIUM/HARD) -> Integer (1-5)

Conversion logic for Float to Integer:
    difficulty <= 0.25 -> 1 (Beginner)
    difficulty <= 0.45 -> 2 (Easy)
    difficulty <= 0.55 -> 3 (Medium)  -- default 0.5 maps to 3
    difficulty <= 0.75 -> 4 (Hard)
    difficulty > 0.75  -> 5 (Expert)

Conversion logic for Enum to Integer:
    EASY   -> 2
    MEDIUM -> 3
    HARD   -> 4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase2_difficulty'
down_revision = '52a620c3043a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add temporary columns for the new integer difficulty
    op.add_column('question_bank', sa.Column('difficulty_level_new', sa.Integer(), nullable=True))
    op.add_column('assessments', sa.Column('difficulty_level_new', sa.Integer(), nullable=True))

    # Step 2: Migrate question_bank.difficulty_level from Float (0.0-1.0) to Integer (1-5)
    # Using raw SQL for the CASE conversion
    op.execute("""
        UPDATE question_bank
        SET difficulty_level_new = CASE
            WHEN difficulty_level <= 0.25 THEN 1
            WHEN difficulty_level <= 0.45 THEN 2
            WHEN difficulty_level <= 0.55 THEN 3
            WHEN difficulty_level <= 0.75 THEN 4
            ELSE 5
        END
    """)

    # Set default for any NULL values
    op.execute("""
        UPDATE question_bank
        SET difficulty_level_new = 3
        WHERE difficulty_level_new IS NULL
    """)

    # Step 3: Migrate assessments.difficulty_level from Enum to Integer (1-5)
    # EASY -> 2, MEDIUM -> 3, HARD -> 4
    op.execute("""
        UPDATE assessments
        SET difficulty_level_new = CASE
            WHEN difficulty_level::text = 'EASY' THEN 2
            WHEN difficulty_level::text = 'MEDIUM' THEN 3
            WHEN difficulty_level::text = 'HARD' THEN 4
            ELSE 3
        END
    """)

    # Set default for any NULL values
    op.execute("""
        UPDATE assessments
        SET difficulty_level_new = 3
        WHERE difficulty_level_new IS NULL
    """)

    # Step 4: Drop the old columns
    op.drop_column('question_bank', 'difficulty_level')
    op.drop_column('assessments', 'difficulty_level')

    # Step 5: Rename new columns to original names
    op.alter_column('question_bank', 'difficulty_level_new', new_column_name='difficulty_level')
    op.alter_column('assessments', 'difficulty_level_new', new_column_name='difficulty_level')

    # Step 6: Set NOT NULL constraints
    op.alter_column('question_bank', 'difficulty_level', nullable=False, server_default='3')
    op.alter_column('assessments', 'difficulty_level', nullable=True)

    # Step 7: Add check constraints for valid difficulty range (1-5)
    op.create_check_constraint(
        'chk_question_bank_difficulty',
        'question_bank',
        'difficulty_level BETWEEN 1 AND 5'
    )
    op.create_check_constraint(
        'chk_assessment_difficulty',
        'assessments',
        'difficulty_level BETWEEN 1 AND 5'
    )

    # Step 8: Drop the old enum type (no longer needed)
    op.execute("DROP TYPE IF EXISTS difficultylevel")

    # Step 9: Create indexes for adaptive querying
    # Index for question_bank: (subtopic_id, difficulty_level) WHERE is_active = true
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_qb_subtopic_difficulty_active
        ON question_bank (subtopic_id, difficulty_level)
        WHERE is_active = true
    """)

    # Update existing index to use integer difficulty
    # First drop the old index
    op.drop_index('idx_qb_subject_topic_difficulty', table_name='question_bank')

    # Recreate with integer difficulty
    op.create_index(
        'idx_qb_subject_topic_difficulty',
        'question_bank',
        ['subject_id', 'topic_id', 'difficulty_level'],
        unique=False
    )


def downgrade() -> None:
    # Step 1: Recreate the enum type
    op.execute("""
        CREATE TYPE difficultylevel AS ENUM ('EASY', 'MEDIUM', 'HARD')
    """)

    # Step 2: Add temporary columns for the old types
    op.add_column('question_bank', sa.Column('difficulty_level_new', sa.Float(), nullable=True))
    op.add_column('assessments', sa.Column('difficulty_level_new', postgresql.ENUM('EASY', 'MEDIUM', 'HARD', name='difficultylevel', create_type=False), nullable=True))

    # Step 3: Convert Integer back to Float for question_bank
    # Map: 1->0.25, 2->0.35, 3->0.5, 4->0.65, 5->0.85
    op.execute("""
        UPDATE question_bank
        SET difficulty_level_new = CASE difficulty_level
            WHEN 1 THEN 0.25
            WHEN 2 THEN 0.35
            WHEN 3 THEN 0.5
            WHEN 4 THEN 0.65
            WHEN 5 THEN 0.85
            ELSE 0.5
        END
    """)

    # Step 4: Convert Integer back to Enum for assessments
    # Map: 1->EASY, 2->EASY, 3->MEDIUM, 4->HARD, 5->HARD
    op.execute("""
        UPDATE assessments
        SET difficulty_level_new = CASE difficulty_level
            WHEN 1 THEN 'EASY'::difficultylevel
            WHEN 2 THEN 'EASY'::difficultylevel
            WHEN 3 THEN 'MEDIUM'::difficultylevel
            WHEN 4 THEN 'HARD'::difficultylevel
            WHEN 5 THEN 'HARD'::difficultylevel
            ELSE 'MEDIUM'::difficultylevel
        END
    """)

    # Step 5: Drop check constraints
    op.drop_constraint('chk_question_bank_difficulty', 'question_bank', type_='check')
    op.drop_constraint('chk_assessment_difficulty', 'assessments', type_='check')

    # Step 6: Drop the integer columns
    op.drop_column('question_bank', 'difficulty_level')
    op.drop_column('assessments', 'difficulty_level')

    # Step 7: Rename new columns to original names
    op.alter_column('question_bank', 'difficulty_level_new', new_column_name='difficulty_level')
    op.alter_column('assessments', 'difficulty_level_new', new_column_name='difficulty_level')

    # Step 8: Set default for assessments
    op.alter_column('assessments', 'difficulty_level', nullable=True)

    # Step 9: Drop and recreate the old index
    op.drop_index('idx_qb_subject_topic_difficulty', table_name='question_bank')
    op.create_index(
        'idx_qb_subject_topic_difficulty',
        'question_bank',
        ['subject_id', 'topic_id', 'difficulty_level'],
        unique=False
    )

    # Step 10: Drop the adaptive query index
    op.drop_index('idx_qb_subtopic_difficulty_active', table_name='question_bank')
