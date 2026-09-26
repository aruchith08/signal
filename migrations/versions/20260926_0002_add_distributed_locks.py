"""Alembic migration to add distributed_locks table"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260926_0002_add_distributed_locks'
down_revision = '20260926_0001_add_user_password_and_role'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'distributed_locks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('locked_by', sa.String(length=100), nullable=False),
        sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_distributed_locks_name', 'distributed_locks', ['name'], unique=True)
    op.create_index('ix_distributed_locks_expires_at', 'distributed_locks', ['expires_at'], unique=False)


def downgrade():
    op.drop_index('ix_distributed_locks_expires_at', table_name='distributed_locks')
    op.drop_index('ix_distributed_locks_name', table_name='distributed_locks')
    op.drop_table('distributed_locks')
