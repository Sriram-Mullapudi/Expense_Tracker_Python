"""Add Alert model for budget tracking and alerts

Revision ID: 002
Revises: 001
Create Date: 2026-01-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add role column to user table
    op.add_column('user', sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))
    op.add_column('user', sa.Column('email', sa.String(length=120)))
    op.add_column('user', sa.Column('created_at', sa.DateTime()))
    
    # Add unique constraint on email
    op.create_unique_constraint('uq_user_email', 'user', ['email'])
    
    # Add columns to expense table
    op.add_column('expense', sa.Column('receipt_path', sa.String(length=500)))
    op.add_column('expense', sa.Column('created_at', sa.DateTime()))
    
    # Create alert table
    op.create_table('alert',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='warning'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_sent', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('triggered_month', sa.String(length=7)),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('alert')
    op.drop_column('expense', 'created_at')
    op.drop_column('expense', 'receipt_path')
    op.drop_constraint('uq_user_email', 'user', type_='unique')
    op.drop_column('user', 'created_at')
    op.drop_column('user', 'email')
    op.drop_column('user', 'role')
