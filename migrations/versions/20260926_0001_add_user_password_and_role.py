"""Alembic migration to add hashed_password and role to users table"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260926_0001_add_user_password_and_role'
down_revision = '20260913_0002_add_scheduler_enabled'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(length=50), nullable=False, server_default=sa.text("'user'")))


def downgrade():
    op.drop_column('users', 'role')
    op.drop_column('users', 'hashed_password')
