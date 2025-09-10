from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Create ENUM types for PostgreSQL
    if dialect_name == 'postgresql':
        user_role = postgresql.ENUM('admin', 'user', name='user_role', create_type=False)
        activation_status = postgresql.ENUM('pending', 'active', 'expired', 'revoked', name='activation_status', create_type=False)
        user_role.create(bind, checkfirst=True)
        activation_status.create(bind, checkfirst=True)

    # accounts table
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'user', name='user_role'), nullable=False, server_default='user'),
        sa.Column('activation_code', sa.String(length=255), nullable=True),
        sa.Column('expired_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activation_status', sa.Enum('pending', 'active', 'expired', 'revoked', name='activation_status'), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_accounts_email_unique', 'accounts', ['email'], unique=True)

    # activation_codes table
    op.create_table(
        'activation_codes',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('activation_code', sa.String(length=32), nullable=False, unique=True),
        sa.Column('user_email', sa.String(length=255), sa.ForeignKey('accounts.email'), nullable=True),
        sa.Column('activation_status', sa.Enum('pending', 'active', 'expired', 'revoked', name='activation_status'), nullable=False, server_default='pending'),
        sa.Column('expiry_date', sa.String(length=64), nullable=True),
        sa.Column('activation_time', sa.String(length=64), nullable=True),
        sa.Column('valid_days', sa.Integer(), nullable=False),
        sa.Column('create_time', sa.String(length=64), nullable=False),
        sa.Column('update_time', sa.String(length=64), nullable=False),
    )
    op.create_index('ix_activation_codes_code_unique', 'activation_codes', ['activation_code'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index('ix_activation_codes_code_unique', table_name='activation_codes')
    op.drop_table('activation_codes')

    op.drop_index('ix_accounts_email_unique', table_name='accounts')
    op.drop_table('accounts')

    # Drop ENUM types for PostgreSQL
    if dialect_name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS activation_status')
        op.execute('DROP TYPE IF EXISTS user_role')
