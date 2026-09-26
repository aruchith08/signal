'''Add scheduled_jobs table'''

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260913_0001_add_scheduled_job'
down_revision = '20230912_02_add_notification_deliveries'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('source_id', sa.String(length=36), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', index=True),
        sa.Column('items_discovered', sa.Integer, nullable=False, server_default='0'),
        sa.Column('items_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
    )

def downgrade():
    op.drop_table('scheduled_jobs')
