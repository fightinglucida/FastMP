# PostgreSQL 常用查询手册（mp_accounts / mp_articles）

说明：本手册整理了在 PostgreSQL 上查看与导出公众号账号与文章数据的常用 SQL 与 psql 命令。请根据实际库名/用户/主机进行调整。

---

## 连接数据库（psql）

- 使用环境变量：
  - `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`
- 直接连接示例（请替换主机/端口/库名/用户）：

```bash
psql "postgresql://<user>:<password>@<host>:<port>/<database>"
```

- 连接后查看当前 schema 与表：
```sql
-- 当前 schema 搜索路径
SHOW search_path;

-- 查看所有表（当前 schema）
\dt

-- 仅查看 mp_* 相关表
\dt mp_*
```

> 如果表不在 `public` schema 下，请先执行：
```sql
SET search_path TO public, "$user";
```

---

## 表结构与索引

- mp_accounts 表结构：
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'mp_accounts'
ORDER BY ordinal_position;
```

- mp_articles 表结构：
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'mp_articles'
ORDER BY ordinal_position;
```

- 索引信息：
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('mp_accounts', 'mp_articles')
ORDER BY tablename, indexname;
```

---

## 快速查看文章数据

- 最近 20 条文章：
```sql
SELECT id, title, url, item_show_type, mp_account, publish_date, create_time
FROM mp_articles
ORDER BY create_time DESC
LIMIT 20;
```

- 分页查看（第 N 页，每页 20 条）：
```sql
-- 替换 :page 为具体页码（从 1 开始）
SELECT id, title, url, item_show_type, mp_account, publish_date, create_time
FROM mp_articles
ORDER BY create_time DESC
LIMIT 20 OFFSET ((:page - 1) * 20);
```

- 指定公众号最近 50 条：
```sql
SELECT id, title, item_show_type, publish_date, url
FROM mp_articles
WHERE mp_account = '你的公众号名称'
ORDER BY create_time DESC
LIMIT 50;
```

- 模糊匹配公众号：
```sql
SELECT id, title, item_show_type, publish_date, url, mp_account
FROM mp_articles
WHERE mp_account ILIKE '%日报%'
ORDER BY create_time DESC
LIMIT 50;
```

---

## item_show_type 类型说明与统计

- 类型含义：
  - 0 = 文章
  - 8 = 图文
  - 11 = 转载

- 直接查看各类型样例：
```sql
SELECT id, title, item_show_type, mp_account
FROM mp_articles
WHERE item_show_type IN (0, 8, 11)
ORDER BY create_time DESC
LIMIT 50;
```

- 统计各类型数量：
```sql
SELECT item_show_type, COUNT(*) AS cnt
FROM mp_articles
GROUP BY item_show_type
ORDER BY item_show_type;
```

- 统计且转换为中文类型说明：
```sql
SELECT CASE item_show_type
         WHEN 0  THEN '文章'
         WHEN 8  THEN '图文'
         WHEN 11 THEN '转载'
         ELSE '未知'
       END AS type_name,
       COUNT(*) AS cnt
FROM mp_articles
GROUP BY type_name
ORDER BY type_name;
```

---

## 按公众号分组统计

- 每个公众号的文章总数（Top 20）：
```sql
SELECT mp_account, COUNT(*) AS cnt
FROM mp_articles
GROUP BY mp_account
ORDER BY cnt DESC
LIMIT 20;
```

- 指定公众号最近 7 天的文章列表：
```sql
SELECT id, title, item_show_type, publish_date, create_time
FROM mp_articles
WHERE mp_account = '你的公众号名称'
  AND create_time >= NOW() - INTERVAL '7 days'
ORDER BY create_time DESC;
```

- 最近 7 天新增文章总数：
```sql
SELECT COUNT(*)
FROM mp_articles
WHERE create_time >= NOW() - INTERVAL '7 days';
```

---

## 联表查看账号信息

- 文章 + 账号头像信息：
```sql
SELECT a.title,
       a.item_show_type,
       a.publish_date,
       a.url,
       acc.name AS account_name,
       acc.avatar_url,
       acc.avatar,
       a.create_time
FROM mp_articles a
JOIN mp_accounts acc ON a.mp_account = acc.name
ORDER BY a.create_time DESC
LIMIT 50;
```

- 查看账号基本信息：
```sql
SELECT id, name, biz, description, owner_email, avatar_url, avatar, article_account, create_time, update_time
FROM mp_accounts
ORDER BY create_time DESC
LIMIT 50;
```

---

## 去重/质量检查

- 检查 URL 唯一性（存在重复时应返回结果，一般应为 0 条）：
```sql
SELECT url, COUNT(*) AS cnt
FROM mp_articles
GROUP BY url
HAVING COUNT(*) > 1;
```

- 检查空类型（未解析到 item_show_type）：
```sql
SELECT COUNT(*) AS null_types
FROM mp_articles
WHERE item_show_type IS NULL;
```

---

## 导出 CSV（psql 中执行）

- 导出文章为 CSV（带表头）：
```sql
\copy (
  SELECT id, title, url, item_show_type, mp_account, publish_date, create_time
  FROM mp_articles
  ORDER BY create_time DESC
) TO './mp_articles.csv' CSV HEADER;
```

- 导出指定公众号最近 30 天文章：
```sql
\copy (
  SELECT id, title, url, item_show_type, mp_account, publish_date, create_time
  FROM mp_articles
  WHERE mp_account = '你的公众号名称'
    AND create_time >= NOW() - INTERVAL '30 days'
  ORDER BY create_time DESC
) TO './mp_articles_last30d.csv' CSV HEADER;
```

> 在 psql 中，`\copy` 以客户端为基准保存文件（即保存到你执行 psql 的那台机器的当前目录）。

---

## 常见问题

- 看不到表：确认 search_path 是否包含目标 schema，或用 schema 限定（例如 `public.mp_articles`）。
- 权限不足：确认连接用户对表有 SELECT 权限，对 `\copy` 的目标路径有写权限（客户端导出不需要服务端写权限）。
- 时间筛选：`publish_date` 为字符串（ISO），如需严格按时间范围筛选，建议使用 `create_time`（带时区的时间戳）。

---

如需我为你的库生成“自定义统计报表 SQL（例如按类型/天汇总）”或“视图（view）/物化视图（materialized view）”，告诉我需求即可！
