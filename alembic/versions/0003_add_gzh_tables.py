from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
    )

    # mp_accounts table
    op.create_table(
        'mp_accounts',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('biz', sa.String(length=64), nullable=False, unique=True),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('category_id', sa.String(length=36), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('owner_email', sa.String(length=255), sa.ForeignKey('accounts.email'), nullable=False),
        sa.Column('create_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('update_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('avatar_url', sa.String(length=1024), nullable=True),
        sa.Column('avatar', sa.String(length=1024), nullable=True),
        sa.Column('article_account', sa.Integer(), nullable=False, server_default=sa.text('0')),
    )
    op.create_index('ix_mp_accounts_name_unique', 'mp_accounts', ['name'], unique=True)
    op.create_index('ix_mp_accounts_biz_unique', 'mp_accounts', ['biz'], unique=True)

    # mp_articles table
    op.create_table(
        'mp_articles',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=False, unique=True),
        sa.Column('cover_url', sa.String(length=1024), nullable=True),
        sa.Column('publish_date', sa.String(length=64), nullable=True),
        sa.Column('item_show_type', sa.String(length=32), nullable=True),
        sa.Column('mp_account', sa.String(length=255), sa.ForeignKey('mp_accounts.name'), nullable=False),
        sa.Column('create_time', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_mp_articles_url_unique', 'mp_articles', ['url'], unique=True)
    op.create_index('ix_mp_articles_account', 'mp_articles', ['mp_account'])


def downgrade() -> None:
    op.drop_index('ix_mp_articles_account', table_name='mp_articles')
    op.drop_index('ix_mp_articles_url_unique', table_name='mp_articles')
    op.drop_table('mp_articles')

    op.drop_index('ix_mp_accounts_biz_unique', table_name='mp_accounts')
    op.drop_index('ix_mp_accounts_name_unique', table_name='mp_accounts')
    op.drop_table('mp_accounts')

    op.drop_table('categories')
