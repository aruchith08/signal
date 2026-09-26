"""Alembic migration to add scheduler_enabled column to sources"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260913_0002_add_scheduler_enabled'
down_revision = '20260913_0001_add_scheduled_job'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sources', sa.Column('scheduler_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')) )


def downgrade():
    op.drop_column('sources', 'scheduler_enabled')
