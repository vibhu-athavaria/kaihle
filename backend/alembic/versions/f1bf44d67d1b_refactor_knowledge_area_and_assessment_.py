"""refactor knowledge_area and assessment_question

Revision ID: f1bf44d67d1b
Revises: 50eee453aba1
Create Date: 2025-10-14 22:09:31.937663

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1bf44d67d1b'
down_revision = '50eee453aba1'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Rename table knowledge_areas → question_bank
    op.rename_table('knowledge_areas', 'question_bank')

    # 2. Drop column difficulty_order from question_bank
    op.drop_column('question_bank', 'difficulty_order')

    # 3. Add moved columns to question_bank
    op.add_column('question_bank', sa.Column('question_text', sa.Text(), nullable=False))
    op.add_column('question_bank', sa.Column('question_type', sa.String(), nullable=False))
    op.add_column('question_bank', sa.Column('options', sa.JSON(), nullable=True))
    op.add_column('question_bank', sa.Column('correct_answer', sa.Text(), nullable=False))
    op.add_column('question_bank', sa.Column('difficulty_level', sa.Float(), nullable=True))

    # 4. Rename foreign key column in assessment_questions
    op.alter_column('assessment_questions', 'knowledge_area_id',
                    new_column_name='question_bank_id')

    # 5. Drop now redundant columns from assessment_questions
    op.drop_column('assessment_questions', 'question_text')
    op.drop_column('assessment_questions', 'question_type')
    op.drop_column('assessment_questions', 'options')
    op.drop_column('assessment_questions', 'correct_answer')
    op.drop_column('assessment_questions', 'difficulty_level')


def downgrade():
    # Reverse the upgrade changes

    # 1. Re-add removed columns to assessment_questions
    op.add_column('assessment_questions', sa.Column('difficulty_level', sa.String(), nullable=False))
    op.add_column('assessment_questions', sa.Column('correct_answer', sa.Text(), nullable=False))
    op.add_column('assessment_questions', sa.Column('options', sa.JSON(), nullable=True))
    op.add_column('assessment_questions', sa.Column('question_type', sa.String(), nullable=False))
    op.add_column('assessment_questions', sa.Column('question_text', sa.Text(), nullable=False))

    # 2. Rename question_bank_id → knowledge_area_id
    op.alter_column('assessment_questions', 'question_bank_id',
                    new_column_name='knowledge_area_id')

    # 3. Drop new columns from question_bank
    op.drop_column('question_bank', 'difficulty_level')
    op.drop_column('question_bank', 'correct_answer')
    op.drop_column('question_bank', 'options')
    op.drop_column('question_bank', 'question_type')
    op.drop_column('question_bank', 'question_text')

    # 4. Add back difficulty_order
    op.add_column('question_bank', sa.Column('difficulty_order', sa.Integer(), nullable=True))

    # 5. Rename question_bank → knowledge_areas
    op.rename_table('question_bank', 'knowledge_areas')
