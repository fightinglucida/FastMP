from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cookies',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False, unique=True),
        sa.Column('owner_email', sa.String(length=255), sa.ForeignKey('accounts.email'), nullable=False),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expire_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=1024), nullable=True),
        sa.Column('avatar', sa.String(length=1024), nullable=True),
        sa.Column('local', sa.String(length=1024), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_cookies_owner_is_current', 'cookies', ['owner_email', 'is_current'])
    op.create_index('ix_cookies_token', 'cookies', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_cookies_owner_is_current', table_name='cookies')
    op.drop_index('ix_cookies_token', table_name='cookies')
    op.drop_table('cookies')
