# Alembic 使用指南（本项目）

本指南介绍如何在本项目中使用 Alembic 管理数据库迁移。当前项目已经初始化 Alembic，并提供了首个迁移脚本，覆盖 `accounts` 与 `activation_codes` 两张表以及相关枚举类型。

注意：应你的要求，当前仍保留了应用启动时的 `Base.metadata.create_all(...)`（用于开发快速起步）。生产环境建议仅通过 Alembic 管理迁移，后续可再切换。

---

## 目录结构与关键文件
- `alembic.ini`：Alembic 配置文件（脚本位置、日志等）
- `alembic/env.py`：加载应用配置（读取 `.env` 中的 `DATABASE_URL`），引入 `Base.metadata` 支持自动比对
- `alembic/versions/0001_initial_accounts_activation_codes.py`：首个迁移脚本（创建表与索引、PostgreSQL 枚举类型）
- 应用模型元数据：`app/db/base.py`（务必在此文件中 import 所有 ORM 模型，以便 Alembic 能发现它们）

## 前置条件
1. 安装依赖
   - `pip install -r requirements.txt`（包含 `alembic`）
2. 配置数据库连接
   - `.env` 中设置：`DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/wechat_collector`
3. 确保数据库可访问，并拥有 DDL 权限（创建表/类型/索引等）

## 常用命令速查
- 初始化（已完成，无需再次执行）
  - 已有：`alembic.ini`、`alembic/` 目录 与 `versions/` 存在
- 查看当前版本：`alembic current`
- 查看历史：`alembic history`
- 升级到最新：`alembic upgrade head`
- 回滚一个版本：`alembic downgrade -1`
- 回滚到基线：`alembic downgrade base`
- 生成新迁移（自动比对）：`alembic revision --autogenerate -m "your message"`
- 生成空迁移（手写）：`alembic revision -m "your message"`
- 给现有数据库“打标签”（不执行 DDL，仅记录版本）：`alembic stamp head` 或 `alembic stamp <revision>`

## 升级本地/服务器数据库
1. 确保 `.env` 中 `DATABASE_URL` 正确
2. 执行：`alembic upgrade head`
3. 验证：
   - `alembic current` 查看当前版本
   - `psql` 中检查表结构、索引、枚举是否存在

## 开发工作流（模型更新 -> 生成迁移 -> 审阅 -> 执行）
1. 修改 ORM 模型（例如 `app/models/*.py`）
2. 确保 `app/db/base.py` 里 import 了对应模型（否则 Alembic 无法感知变更）
3. 生成迁移脚本
   - `alembic revision --autogenerate -m "add xyz"`
4. 审阅并完善迁移脚本（非常重要）
   - 自动比对可能对枚举类型、索引命名、server_default 等不完全，必要时手工编辑
5. 执行迁移
   - 本地：`alembic upgrade head`
   - 服务器：将代码与迁移脚本部署后执行同样命令

## 示例 A：为 activation_codes 增加备注列
1. 修改模型（示例）：
   - 在 `app/models/activation_code.py` 的 `ActivationCode` 中新增：
     ```python
     from sqlalchemy import String
     remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
     ```
2. 生成迁移：
   - `alembic revision --autogenerate -m "add remark to activation_codes"`
3. 审阅迁移：确认出现 `op.add_column('activation_codes', ...)` 并无误
4. 执行：`alembic upgrade head`

## 示例 B：为枚举类型新增值（PostgreSQL）
- 例如给 `activation_status` 增加新值 `suspended`
- 自动比对对 PostgreSQL ENUM 的支持有限，建议手写迁移：
  1. 生成空迁移：`alembic revision -m "extend activation_status enum"`
  2. 在生成的脚本中（`upgrade()`）：
     ```python
     from alembic import op
     op.execute("ALTER TYPE activation_status ADD VALUE IF NOT EXISTS 'suspended'")
     ```
  3. 若需要降级（`downgrade()`）
     - PostgreSQL ENUM 不支持直接删除值，通常以文档方式记录“不可降级”，或通过创建新类型并重建列（较重，不推荐）。

## 生产环境建议
- 使用 Alembic 统一管理迁移，避免依赖应用启动的 `create_all`（你已要求暂不移除，后续可切换）
- 每次上新前：先执行 `alembic upgrade head`，失败则回滚
- 为重要版本做好数据库备份与回滚预案
- CI/CD：
  - 构建阶段运行 `alembic upgrade head` 针对测试数据库
  - 部署阶段对生产数据库执行迁移
- 权限最小化：生产数据库账号仅授予必要 DDL 权限

## 多环境数据库与配置
- `alembic/env.py` 会优先使用 `alembic.ini` 里的 `sqlalchemy.url`，若为空则回落到应用配置 `settings.DATABASE_URL`
- 建议通过环境变量切换不同环境的 `DATABASE_URL`

## 常见问题与排查
- Autogenerate 未检测到变更
  - 确保模型文件已被 `app/db/base.py` import
  - 确保运行命令的工作目录是项目根目录
- 连接失败（认证 / 权限）
  - 校验 `DATABASE_URL`、pg_hba.conf、用户密码、端口
- PostgreSQL ENUM
  - 变更枚举值请使用手写迁移；降级通常需要新建类型 + 重建列
- 迁移冲突（多头）
  - 出现 "Multiple heads are present" 时，使用 `alembic merge -m "merge heads" <rev1> <rev2>` 合并
- Windows/PowerShell 使用
  - 如 `alembic` 不在 PATH，可使用模块方式运行：`python -m alembic upgrade head`

## 与应用启动自动建表的关系
- 当前仍保留自动建表便于本地开发
- 当开始在某环境使用 Alembic，请优先通过 `alembic upgrade head` 管理表结构
- 避免让“自动建表”和“迁移脚本”在同一环境同时修改结构（先运行迁移，再考虑取消自动建表）

---

## 命令清单（可复制）
- 升级到最新：
  ```bash
  alembic upgrade head
  ```
- 回滚一步：
  ```bash
  alembic downgrade -1
  ```
- 生成自动迁移：
  ```bash
  alembic revision --autogenerate -m "describe change"
  ```
- 生成空迁移（手写）：
  ```bash
  alembic revision -m "manual change"
  ```
- 打标签到最新（不执行 DDL）：
  ```bash
  alembic stamp head
  ```

---

如需我将这份指南同步到 README 或生成 Confluence 页面，请告诉我。
