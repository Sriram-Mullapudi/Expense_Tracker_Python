"""Add email field and enhancements - Migration 003."""
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Upgrade database schema."""
    # Add email field to user table if not exists
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Check if email column already exists
        try:
            batch_op.add_column(sa.Column('email', sa.String(120), nullable=True))
            batch_op.create_unique_constraint('uq_user_email', ['email'])
        except:
            pass


def downgrade():
    """Downgrade database schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('uq_user_email', type_='unique')
            batch_op.drop_column('email')
        except:
            pass
