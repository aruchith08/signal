"""Alembic migration to add unique constraints for ingestion idempotency"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260926_0003_add_ingestion_idempotency_constraints'
down_revision = '20260926_0002_add_distributed_locks'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'uq_raw_discoveries_content_hash_canonical_url',
        'raw_discoveries',
        ['content_hash', 'canonical_url'],
        unique=True,
    )
    op.create_index(
        'uq_opportunity_events_opp_content_hash',
        'opportunity_events',
        ['opportunity_id', 'content_hash'],
        unique=True,
    )


def downgrade():
    op.drop_index('uq_opportunity_events_opp_content_hash', table_name='opportunity_events')
    op.drop_index('uq_raw_discoveries_content_hash_canonical_url', table_name='raw_discoveries')
