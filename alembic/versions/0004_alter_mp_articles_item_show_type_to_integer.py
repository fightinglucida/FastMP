from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        # 清理空字符串，避免转换失败
        op.execute("UPDATE mp_articles SET item_show_type = NULL WHERE item_show_type = ''")
        # 将列类型改为 integer（保留 NULL）
        op.execute(
            "ALTER TABLE mp_articles "
            "ALTER COLUMN item_show_type TYPE integer USING NULLIF(item_show_type, '')::integer"
        )
    elif dialect_name == 'sqlite':
        # SQLite 变更列类型较为复杂，通常需要重建表。这里跳过，保留现状。
        # 如果需要在 SQLite 上强制转换，请单独执行重建表逻辑。
        pass
    else:
        # 其他方言：尝试通用 ALTER（可能不支持 USING 语法）
        try:
            op.execute("ALTER TABLE mp_articles ALTER COLUMN item_show_type TYPE integer")
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        # 恢复为可变长字符串
        op.execute(
            "ALTER TABLE mp_articles ALTER COLUMN item_show_type TYPE varchar(32) USING item_show_type::varchar"
        )
    elif dialect_name == 'sqlite':
        # 同上，跳过
        pass
    else:
        try:
            op.execute("ALTER TABLE mp_articles ALTER COLUMN item_show_type TYPE varchar(32)")
        except Exception:
            pass
