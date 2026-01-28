"""add trial extensions and registration completed

Revision ID: 71bfcaf277f8_add_trial_extensions_and_registration_completed
Revises: e4c91a0f1d23
Create Date: 2026-01-25 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71bfcaf277f8'
down_revision = 'e4c91a0f1d23'
branch_labels = None
depends_on = None


def upgrade() -> None:

    # Create trial_extensions table
    op.create_table('trial_extensions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subscription_id', sa.Integer(), nullable=False),
    sa.Column('extended_by_admin_id', sa.Integer(), nullable=False),
    sa.Column('original_trial_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('new_trial_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('extension_days', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
    sa.ForeignKeyConstraint(['extended_by_admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trial_extensions_id'), 'trial_extensions', ['id'], unique=False)

    # Update yearly_discount default in subscription_plans
    op.execute("UPDATE subscription_plans SET yearly_discount = 20.00 WHERE yearly_discount = 10.00")


def downgrade() -> None:
    # Drop trial_extensions table
    op.drop_index(op.f('ix_trial_extensions_id'), table_name='trial_extensions')
    op.drop_table('trial_extensions')

    # Revert yearly_discount back to 10.00
    op.execute("UPDATE subscription_plans SET yearly_discount = 10.00 WHERE yearly_discount = 20.00")