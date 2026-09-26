"""Alembic migration to add in-app read status and timestamp columns to notifications table"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260926_0004_add_notification_inapp_read_status'
down_revision = '20260926_0003_add_ingestion_idempotency_constraints'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('read_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('user_status', sa.String(length=20), server_default='unread', nullable=False))
        batch_op.create_index('ix_notifications_user_status', ['user_status'], unique=False)


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_user_status')
        batch_op.drop_column('user_status')
        batch_op.drop_column('dismissed_at')
        batch_op.drop_column('read_at')
