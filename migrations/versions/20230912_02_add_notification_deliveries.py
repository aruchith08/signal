'''Alembic migration to add notification_deliveries table'''

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20230912_02_add_notification_deliveries'
down_revision = '20230912_01_add_change_sets'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'notification_deliveries',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('notification_id', sa.String(length=36), sa.ForeignKey('notifications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('channel', sa.String(length=50), nullable=False, server_default='telegram', index=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending', index=True),
        sa.Column('attempt_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('channel_identifier', sa.String(length=255), nullable=True),
    )

def downgrade():
    op.drop_table('notification_deliveries')
