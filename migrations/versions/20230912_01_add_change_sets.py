'''Alembic migration to add change_sets table'''

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20230912_01_add_change_sets'
down_revision = '796ad5bd0e2b'  # Updated to point to Phase 4 head
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'change_sets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('opportunity_id', sa.String(length=36), sa.ForeignKey('opportunities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_discovery_id', sa.String(length=36), sa.ForeignKey('source_snapshots.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('field_name', sa.String(length=255), nullable=False, index=True),
        sa.Column('previous_value', sa.Text, nullable=True),
        sa.Column('new_value', sa.Text, nullable=True),
        sa.Column('change_type', sa.String(length=50), nullable=False, server_default='no_change', index=True),
        sa.Column('importance', sa.String(length=20), nullable=False, server_default='medium', index=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved', sa.Boolean, nullable=False, server_default=sa.text('false'))
    )

def downgrade():
    op.drop_table('change_sets')
