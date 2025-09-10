# FastAPI 基础框架

本目录提供一个最小可运行的 FastAPI 基础框架，包含：
- 健康检查接口 `/health`
- 环境与配置管理（Pydantic Settings）
- CORS 支持
- 数据库会话占位（SQLAlchemy）

## 运行步骤

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 复制环境变量模板并按需修改

```bash
cp .env.example .env
```

3. 启动服务（开发模式）

```bash
uvicorn app.main:app --reload --port 8000
```

4. 访问
- 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 目录结构

```
app/
├── api/                    # API 层
│   ├── deps.py             # 依赖（如数据库会话注入）
│   └── v1/
│       └── routes/
│           └── health.py   # 健康检查路由
├── core/                   # 核心配置
│   └── config.py           # Pydantic Settings 配置
├── db/                     # 数据库相关
│   ├── base.py             # SQLAlchemy Base 定义
│   └── session.py          # 会话（SessionLocal）与引擎
├── models/                 # SQLAlchemy 模型（占位）
├── schemas/                # Pydantic 模型
│   └── health.py           # 健康检查响应模型
├── services/               # 业务服务（占位）
├── utils/                  # 工具方法（占位）
└── main.py                 # 应用入口，注册中间件与路由

requirements.txt           # 依赖列表
.env.example               # 环境变量模板
```

## 常见扩展
- 用户/认证：添加 `auth` 路由、JWT 工具、用户模型/表
- 业务模块：在 `services/` 编写领域服务，并在 `routes/` 暴露 API
- 数据库：切换到 PostgreSQL（设置 `DATABASE_URL`），新增 Alembic 迁移
- 任务队列：引入 Celery + Redis，定义异步任务

## 测试
`tests/test_health.py` 为简单连通性测试（需服务已启动）。

---

╭─ Response ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 进度说明：我已在项目中完成账号模型、注册/登录接口、JWT 认证、密码哈希、数据库初始化钩子、PostgreSQL                  │
│ 连接与环境变量配置，并保留了“激活码 + 有效期 + 激活状态”的数据结构，为后续“激活码认证”接口打好基础。                 │
│                                                                                                                      │
│ 本次新增/修改的文件                                                                                                  │
│                                                                                                                      │
│  • app/models/account.py: 账号表模型（包含你要求的字段）                                                             │
│  • app/schemas/account.py: 注册输入、账号输出 Schema                                                                 │
│  • app/schemas/auth.py: 登录输入、Token 输出 Schema                                                                  │
│  • app/services/security.py: 密码哈希（bcrypt）、JWT 生成                                                            │
│  • app/services/auth.py: 注册与登录业务逻辑                                                                          │
│  • app/api/v1/routes/auth.py: 注册 /auth/register 与 登录 /auth/login API                                            │
│  • app/api/deps.py: 新增 OAuth2/JWT 解析、获取当前用户与“激活用户校验”依赖                                           │
│  • app/main.py: 注册 auth 路由、启动时自动建表                                                                       │
│  • app/db/base.py: 确保模型在 metadata.create_all 中被发现                                                           │
│  • .env.example: 增加 PostgreSQL、JWT 配置示例                                                                       │
│  • requirements.txt: 新增 python-jose、passlib[bcrypt]、psycopg[binary]                                              │
│                                                                                                                      │
│ 数据表设计（account）                                                                                                │
│                                                                                                                      │
│  • id: UUID 字符串主键（String(36)，默认 uuid4）                                                                     │
│  • email: 唯一索引（String(255)）                                                                                    │
│  • password_hash: 使用 bcrypt 存储                                                                                   │
│  • role: 用户角色（admin/user，枚举）                                                                                │
│  • activation_code: 激活码（可为空）                                                                                 │
│  • expired_time: 激活有效截止时间（带时区）                                                                          │
│  • activation_status: 激活状态（pending/active/expired/revoked）                                                     │
│  • created_at/updated_at: 创建与更新时间                                                                             │
│                                                                                                                      │
│ 已实现的接口                                                                                                         │
│                                                                                                                      │
│  • POST /auth/register                                                                                               │
│     • 请求: { "email": "user@example.com", "password": "secret123" }                                                 │
│     • 返回: 账号基本信息（不含密码）                                                                                 │
│  • POST /auth/login                                                                                                  │
│     • 请求: { "email": "user@example.com", "password": "secret123" }                                                 │
│     • 返回: { "access_token": "JWT...", "token_type": "bearer" }                                                     │
│                                                                                                                      │
│ 认证与授权说明                                                                                                       │
│                                                                                                                      │
│                                                                                                                      │
│  • 登录成功返回 JWT，后续请求通过 Authorization: Bearer  访问受保护资源。                                            │
│  • 我已提供依赖 require_active_user，用于在具体路由上强制“账号已激活且未过期”的要求。你可在任意路由加上              │
│    dependencies=[Depends(require_active_user)] 即可强制认证与激活校验。                                              │
│  • 目前 /auth/* 开放用于注册与登录；健康检查 /health                                                                 │
│    暂未强制认证，以便基础监控。若需要全站强制认证，我可以按你的偏好以“全局依赖”或“中间件白名单”方式实现（如下“下一步 │
│    建议”）。                                                                                                         │
│                                                                                                                      │
│ 运行步骤（Win10 开发 / Ubuntu 生产）                                                                                 │
│                                                                                                                      │
│  1 安装依赖                                                                                                          │
│                                                                                                                      │
│  • pip install -r requirements.txt                                                                                   │
│                                                                                                                      │
│  2 配置环境变量                                                                                                      │
│                                                                                                                      │
│  • 复制 env 模板: cp .env.example .env                                                                               │
│  • 设置 PostgreSQL 连接（示例）:                                                                                     │
│     • DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/wechat_collector                       │
│  • 设置 JWT 密钥:                                                                                                    │
│     • JWT_SECRET=一个足够随机的长字符串                                                                              │
│     • JWT_ALGORITHM=HS256                                                                                            │
│     • ACCESS_TOKEN_EXPIRE_MINUTES=1440                                                                               │
│  • CORS 可按需调整 BACKEND_CORS_ORIGINS（JSON 数组）                                                                 │
│                                                                                                                      │
│  3 启动服务                                                                                                          │
│                                                                                                                      │
│  • uvicorn app.main:app --reload --port 8000                                                                         │
│  • 首次启动会自动执行 Base.metadata.create_all(...) 建表                                                             │
│  • Ubuntu 生产建议改为 Alembic 管理迁移（见下“下一步建议”）                                                          │
│                                                                                                                      │
│  4 快速验证                                                                                                          │
│                                                                                                                      │
│  • 注册                                                                                                              │
│     • curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d                        │
│       '{"email":"test@ex.com","password":"secret123"}'                                                               │
│  • 登录                                                                                                              │
│     • curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d                           │
│       '{"email":"test@ex.com","password":"secret123"}'                                                               │
│     • 得到 access_token 后，在受保护接口中使用                                                                       │
│  • 保护接口用法示例（开发新接口时）                                                                                  │
│     • 在路由函数或 router 上添加 dependencies=[Depends(require_active_user)]                                         │
│     • 例如: from fastapi import Depends from app.api.deps import require_active_user @router.get("/me",              │
│       dependencies=[Depends(require_active_user)]) def me(current=Depends(get_current_user)): return {"id":          │
│       current.id, "email": current.email}                                                                            │
│                                                                                                                      │
│ 注意事项                                                                                                             │
│                                                                                                                      │
│  • OAuth2PasswordBearer 的 tokenUrl 设为 /auth/login，但该端点当前使用 JSON 请求体（而非表单）。这不影响调用，但     │
│    Swagger UI 的“Authorize”按钮不能自动完成登录。如果你需要在 /docs 中通过 OAuth2                                    │
│    流程登录，我可以将登录端点改为标准的 OAuth2PasswordRequestForm（application/x-www-form-urlencoded）。             │
│  • 枚举类型（user_role、activation_status）在 PostgreSQL 中将创建为独立 ENUM 类型。如后续调整枚举值，建议用 Alembic  │
│    迁移处理。                                                                                                        │
│                                                                                                                      │
│ 下一步建议（覆盖你的“必须先认证 + 激活码”需求）                                                                      │
│                                                                                                                      │
│  • 实现“激活码”流程接口：                                                                                            │
│     • POST /auth/activate: 提交 activation_code，更新 activation_status=active、设置 expired_time                    │
│     • 校验 activation_code 的合法性与有效期；管理员可生成/撤销激活码                                                 │
│     • 可考虑将激活码从 account 表拆分为独立 activation_codes                                                         │
│       表（便于复用、追踪与审计），但目前也可按你现有要求保留在 account 表                                            │
│  • 全站认证拦截：                                                                                                    │
│     • 方案A（推荐）中间件 + 白名单：对 /auth/*、/health、/docs、/openapi.json 放行，其他全部要求 JWT + 激活校验      │
│     • 方案B 全局依赖：在 include_router 时对非 /auth 的 router 统一添加 dependencies=[Depends(require_active_user)]  │
│  • 管理员能力：                                                                                                      │
│     • 生成/查看/撤销激活码、设置有效期、查看账号状态、禁用账号等                                                     │
│  • 迁移与生产最佳实践：                                                                                              │
│     • 引入 Alembic 管理数据库迁移（我可帮你初始化）                                                                  │
│     • 将 JWT_SECRET 放入安全的环境配置/密钥管理                                                                      │
│     • 为注册/登录增加速率限制与审计日志                                                                              │
│  • 测试：                                                                                                            │
│     • 增加注册、登录、受保护接口访问、激活流程的集成测试（使用 TestClient + sqlite 内存库或 Testcontainers           │
│       PostgreSQL）                                                                                                   │
│                                                                                                                      │
│ 需要我现在继续：                                                                                                     │
│                                                                                                                      │
│  1 实现激活码接口（/auth/activate）与管理员生成激活码接口                                                            │
│  2 为除 /auth 与 /health 外的所有接口加“全局认证+激活”拦截（中间件/全局依赖）                                        │
│  3 调整 /auth/login 为标准 OAuth2 表单登录以适配 Swagger UI                                                          │
│  4 初始化 Alembic 迁移（创建 accounts 表的 migration）                                                               │
│  5 创建 PR 并撰写变更说明，或生成一份架构与接口文档（README/Confluence）                                             │
│                                                                                                                      │
│ 我可以帮你：                                                                                                         │
│                                                                                                                      │
│  • 创建一个 Jira 任务追踪“账号激活流程”与“全站认证拦截”的开发                                                        │
│  • 生成 Confluence 页面记录本次改动与后续设计                                                                        │
│  • 为本次提交创建 Git 分支与 Pull Request                                                                            │
│                                                                                                                      │
│ 你希望我先做哪一项？要我先实现“激活码接口 + 全站拦截”还是先补充 Alembic 迁移与文档？                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


---

╭─ Response ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 好的，我来给你一份在 Ubuntu 服务器上创建 PostgreSQL 数据库与账号表的完整操作指南。你可以选择“由应用自动建表”或“手工  │
│ SQL 建表”两种方式，二选一即可。建议你在生产环境后续引入 Alembic 管理迁移，但现在我们先把表建起来。                   │
│                                                                                                                      │
│ 一、准备工作（服务器上）                                                                                             │
│                                                                                                                      │
│  1 确认 PostgreSQL 正常运行                                                                                          │
│                                                                                                                      │
│  • sudo systemctl status postgresql                                                                                  │
│  • sudo -u postgres psql -c "SELECT version();"                                                                      │
│                                                                                                                      │
│  2 创建数据库与用户                                                                                                  │
│                                                                                                                      │
│  • 进入 psql: sudo -u postgres psql                                                                                  │
│  • 在 psql 中执行： CREATE DATABASE wechat_collector; CREATE USER wechat_user WITH ENCRYPTED PASSWORD                │
│    '请设置一个强密码'; GRANT ALL PRIVILEGES ON DATABASE wechat_collector TO wechat_user; \c wechat_collector GRANT   │
│    USAGE, CREATE ON SCHEMA public TO wechat_user; ALTER DATABASE wechat_collector OWNER TO wechat_user;              │
│  • 退出： \q                                                                                                         │
│                                                                                                                      │
│  3 可选（远程访问数据库）                                                                                            │
│                                                                                                                      │
│  • 如果你需要从其他机器连接该 PostgreSQL（比如你的 Win10 开发机），需要修改配置：                                    │
│     • 编辑 /etc/postgresql/<版本>/main/postgresql.conf，确保： listen_addresses = '*'                                │
│     • 编辑 /etc/postgresql/<版本>/main/pg_hba.conf，添加（用你的网段替换）： host    wechat_collector    wechat_user │
│       10.0.0.0/24    scram-sha-256                                                                                   │
│     • 重启服务： sudo systemctl restart postgresql                                                                   │
│  • 如果只在服务器本机上使用，则无需开启远程访问。                                                                    │
│                                                                                                                      │
│ 二、方式A：由应用自动建表（推荐，最快） 我们的应用启动时会执行 Base.metadata.create_all(bind=engine)                 │
│ 自动创建表。步骤如下：                                                                                               │
│                                                                                                                      │
│  1 设置环境变量（在项目根目录）                                                                                      │
│                                                                                                                      │
│  • 复制环境模板： cp .env.example .env                                                                               │
│  • 编辑 .env，设置 PostgreSQL 连接（根据你的实际用户/密码）：                                                        │
│    DATABASE_URL=postgresql+psycopg://wechat_user:你的密码@localhost:5432/wechat_collector                            │
│  • 设置 JWT（请使用更强的随机字符串）： JWT_SECRET=强随机字符串 JWT_ALGORITHM=HS256 ACCESS_TOKEN_EXPIRE_MINUTES=1440 │
│                                                                                                                      │
│  2 安装依赖                                                                                                          │
│                                                                                                                      │
│  • pip install -r requirements.txt                                                                                   │
│                                                                                                                      │
│  3 启动应用（首次启动会自动建表）                                                                                    │
│                                                                                                                      │
│  • uvicorn app.main:app --host 0.0.0.0 --port 8000                                                                   │
│  • 观察日志，无错误即表示已建表成功。                                                                                │
│                                                                                                                      │
│  4 验证（使用 psql）                                                                                                 │
│                                                                                                                      │
│  • sudo -u postgres psql -d wechat_collector                                                                         │
│  • 在 psql 中执行： \dt \d+ accounts                                                                                 │
│  • 看到 accounts 表结构即成功。                                                                                      │
│                                                                                                                      │
│ 三、方式B：手工 SQL 建表（不用运行应用也可） 如果你希望直接在数据库中手工创建表（与 ORM 模型完全对齐）：             │
│                                                                                                                      │
│  1 连接数据库                                                                                                        │
│                                                                                                                      │
│  • psql "postgresql://wechat_user:你的密码@localhost:5432/wechat_collector"                                          │
│                                                                                                                      │
│  2 执行以下 SQL（注意：我们的模型 id 使用 VARCHAR(36)，不要改为 uuid 类型，否则和 ORM 类型不一致）                   │
│                                                                                                                      │
│  • 复制以下 SQL 并执行： -- 枚举类型 CREATE TYPE user_role AS ENUM ('admin', 'user'); CREATE TYPE activation_status  │
│    AS ENUM ('pending', 'active', 'expired', 'revoked');                                                              │
│    -- 账号表 CREATE TABLE public.accounts ( id                VARCHAR(36) PRIMARY KEY,                -- 由应用生成  │
│    UUID 字符串 email             VARCHAR(255) NOT NULL UNIQUE, password_hash     VARCHAR(255) NOT NULL, role         │
│    user_role NOT NULL DEFAULT 'user', activation_code   VARCHAR(255), expired_time      TIMESTAMPTZ,                 │
│    activation_status activation_status NOT NULL DEFAULT 'pending', created_at        TIMESTAMPTZ NOT NULL DEFAULT    │
│    now(), updated_at        TIMESTAMPTZ );                                                                           │
│    -- 额外索引（唯一约束已自动创建唯一索引，但为了与代码一致，保留此命名索引） DO $$ BEGIN IF NOT EXISTS ( SELECT 1  │
│    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = 'ix_accounts_email_unique' AND    │
│    n.nspname = 'public' ) THEN CREATE UNIQUE INDEX ix_accounts_email_unique ON public.accounts (email); END IF;      │
│    END$$;                                                                                                            │
│    -- 可选：更新 updated_at 的触发器（让数据库在更新时自动填充 updated_at） CREATE OR REPLACE FUNCTION               │
│    set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;        │
│    DROP TRIGGER IF EXISTS trg_accounts_set_updated_at ON public.accounts; CREATE TRIGGER trg_accounts_set_updated_at │
│    BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION set_updated_at();                                  │
│                                                                                                                      │
│  3 验证                                                                                                              │
│                                                                                                                      │
│  • 在 psql 中执行： \dt \d+ accounts                                                                                 │
│  • 确认字段、索引、触发器存在。                                                                                      │
│                                                                                                                      │
│ 四、连接字符串与应用配置                                                                                             │
│                                                                                                                      │
│  • 你的 Win10 开发环境或 Ubuntu 生产环境，统一使用如下连接字符串：                                                   │
│    postgresql+psycopg://wechat_user:你的密码@<主机>:5432/wechat_collector                                            │
│  • 生产建议：                                                                                                        │
│     • 使用强密码，限制 pg_hba.conf 的允许来源网段                                                                    │
│     • 将 JWT_SECRET 放入安全配置（如环境变量或密钥管理服务）                                                         │
│     • 后续用 Alembic 管理迁移（我可以帮你初始化）                                                                    │
│                                                                                                                      │
│ 五、快速初始化管理员账号（可选） 如果你想直接插入一个管理员账号用于登录测试：                                        │
│                                                                                                                      │
│  • 推荐使用应用层以确保密码哈希一致（服务器上项目目录中执行）： python - <<'PY' from sqlalchemy import create_engine │
│    from sqlalchemy.orm import Session from passlib.context import CryptContext from app.models.account import        │
│    Account, UserRole, ActivationStatus from app.core.config import Settings                                          │
│    settings = Settings() engine = create_engine(settings.DATABASE_URL, future=True) pwd =                            │
│    CryptContext(schemes=['bcrypt'], deprecated='auto').hash('AdminPassword123!') with Session(engine) as s: acc =    │
│    Account(email='admin@example.com', password_hash=pwd, role=UserRole.admin,                                        │
│    activation_status=ActivationStatus.active) s.add(acc) s.commit() print("Admin created: admin@example.com /        │
│    AdminPassword123!") PY                                                                                            │
│  • 然后使用 /auth/login 登录以获取 JWT。                                                                             │
│                                                                                                                      │
│ 常见问题                                                                                                             │
│                                                                                                                      │
│  • 连接报错“SCRAM authentication failed”：请确认用户/密码正确，并且 pg_hba.conf 对该来源启用了 scram-sha-256。       │
│  • 表已存在/枚举已存在错误：重复执行 SQL 时可能报错。可以改用“应用自动建表”，或在 SQL                                │
│    前加条件判断（上面索引逻辑已示范）。                                                                              │
│  • 监听不到远程连接：确认 postgresql.conf 的 listen_addresses、pg_hba.conf 规则和防火墙开放了 5432。                 │
│                                                                                                                      │
│ 是否需要我帮你：                                                                                                     │
│                                                                                                                      │
│  • 生成 Alembic 初始迁移（accounts 表 + 枚举类型）                                                                   │
│  • 提供一套“全站认证拦截 + 激活码接口”的进一步实现                                                                   │
│  • 为这份操作指南生成一页 Confluence 文档或创建一个 Jira 任务跟踪“数据库初始化与部署”？                              │
│                                                                                                                      │
│ 你希望采用“应用自动建表”还是“手工 SQL 建表”？需要我帮你现在远程检查你的 PostgreSQL 状态或编写 Alembic 迁移脚本吗？   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

---

> 我已经选择方式A，数据库和数据表已经创建好了，现在可以如何测试当前的代码？当前的运行的日志如下：
(venv) PS F:\linshutech\FastMP> uvicorn app.main:app --host 0.0.0.0 --port 8000
INFO:     Started server process [12268]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

╭─ Response ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 很好，服务已经正常启动。下面给你一套“本地（Win10 PowerShell）+                                                       │
│ 服务器验证”的测试步骤，确保注册/登录/数据库写入都没问题。                                                            │
│                                                                                                                      │
│  1 基础连通性                                                                                                        │
│                                                                                                                      │
│  • 访问接口文档: http://localhost:8000/docs                                                                          │
│  • 健康检查（任选其一）                                                                                              │
│     • PowerShell: Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health"                                  │
│     • curl: curl -i http://localhost:8000/health                                                                     │
│                                                                                                                      │
│  2 注册账号                                                                                                          │
│                                                                                                                      │
│  • PowerShell: $regBody = @{ email="user1@example.com"; password="Secret123!" } | ConvertTo-Json Invoke-RestMethod   │
│    -Method Post -Uri "http://localhost:8000/auth/register" -Body $regBody -ContentType "application/json"            │
│  • curl: curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" -d                   │
│    "{"email":"user1@example.com","password":"Secret123!"}"                                                           │
│  • 预期结果：返回 id、email、role、activation_status 等。若重复注册同一邮箱，会返回 400。                            │
│                                                                                                                      │
│  3 登录获取 JWT                                                                                                      │
│                                                                                                                      │
│  • PowerShell: $loginBody = @{ email="user1@example.com"; password="Secret123!" } | ConvertTo-Json $loginResp =      │
│    Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/login" -Body $loginBody -ContentType              │
│    "application/json" $token = $loginResp.access_token $token                                                        │
│  • curl: curl -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d                      │
│    "{"email":"user1@example.com","password":"Secret123!"}"                                                           │
│  • 预期结果：返回 {"access_token": "...", "token_type": "bearer"}。                                                  │
│  • 可选：在 https://jwt.io 手动解码 access_token，能看到 sub（你的用户ID）、email、role、iat/exp 等字段。            │
│                                                                                                                      │
│  4 验证数据库已写入                                                                                                  │
│                                                                                                                      │
│  • 在服务器 Ubuntu 上检查（任选其一）：                                                                              │
│     • 使用 postgres 超级用户： sudo -u postgres psql -d wechat_collector -c "SELECT                                  │
│       id,email,role,activation_status,created_at FROM accounts ORDER BY created_at DESC LIMIT 5;"                    │
│     • 使用应用用户（替换成你的用户名）： psql "postgresql://wechat_user:你的密码@localhost:5432/wechat_collector" -c │
│       "SELECT id,email,role,activation_status FROM accounts ORDER BY created_at DESC LIMIT 5;"                       │
│                                                                                                                      │
│  5 使用 Token 调用接口（示例） 当前未强制保护任何业务接口；但你可以先演示携带 Authorization 头的调用格式：           │
│                                                                                                                      │
│  • PowerShell 示例（虽然 /health 不需要认证，但演示格式）： $headers = @{ Authorization = "Bearer $token" }          │
│    Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health" -Headers $headers                               │
│  • curl 示例： curl -H "Authorization: Bearer $token" http://localhost:8000/health                                   │
│                                                                                                                      │
│ 如果你想验证“JWT 生效 + 获取当前用户”，我可以帮你加一个 GET /auth/me                                                 │
│ 接口（需要登录即可访问），或一个需要激活状态的受保护接口（依赖 require_active_user）。目前新注册用户的               │
│ activation_status=pending，如果我们添加受保护接口，会因未激活被拒绝（403），这符合你的业务要求。                     │
│                                                                                                                      │
│ 常见问题排查                                                                                                         │
│                                                                                                                      │
│                                                                                                                      │
│  • 连接 PostgreSQL 失败：确认 .env 中                                                                                │
│    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname，且服务可达（本机一般为 localhost）。                │
│  • 500/加密错误：确保已安装 passlib[bcrypt] 与 python-jose[cryptography]，并重启服务。                               │
│  • Swagger UI 无法直接“Authorize”：我们使用 JSON 登录体而非 OAuth2 表单，Swagger 的 Authorize                        │
│    按钮不会自动登录。可以使用上述 PowerShell/curl 拿到 token 后，再手动在请求头里加 Authorization: Bearer            │
│    。如需改为标准 OAuth2PasswordRequestForm，我可以调整端点实现。                                                    │
│                                                                                                                      │
│ 下一步你希望我：                                                                                                     │
│                                                                                                                      │
│  • 添加 /auth/me（验证 JWT）与 /auth/activate（激活码激活）接口，并将除 /auth 和 /health                             │
│    外的接口全部加“认证+激活”保护？                                                                                   │
│  • 初始化 Alembic 迁移，便于生产环境持续演进？                                                                       │
│  • 帮你创建一份测试清单和 Confluence 文档记录“注册/登录/激活/受保护访问”的流程？                                     │
│                                                                                                                      │
│ 你想先加一个 /auth/me 方便验证 JWT，还是直接实现激活码接口并全站拦截？                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

---
> 直接改为“PBKDF2+兼容 bcrypt”的方式，
同时我刚刚测试了登录，登录成功了，但是返回的access_token好长，能否改为返回一个短一些的token ？

╭─ Response ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 已按你的要求完成两项改造：                                                                                           │
│                                                                                                                      │
│  • 将密码哈希改为“PBKDF2-SHA256（默认）+ 兼容 bcrypt”，避免 Windows/Ubuntu 上的 bcrypt 版本告警，同时保留对旧 bcrypt │
│    哈希的验证能力。                                                                                                  │
│  • 缩短 JWT：将 sub 压缩为 22 字符的 base64url UUID，并移除额外自定义声明，只保留 sub/iat/exp，从而显著缩短 token    │
│    长度。并新增了一个便于验证的 /auth/me 接口。                                                                      │
│                                                                                                                      │
│ 你现在可以这样测试                                                                                                   │
│                                                                                                                      │
│  1 注册并登录，观察 token 长度                                                                                       │
│                                                                                                                      │
│  • 注册: curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" -d                   │
│    "{"email":"user2@example.com","password":"Secret123!"}"                                                           │
│  • 登录: TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d           │
│    "{"email":"user2@example.com","password":"Secret123!"}" | python -c "import                                       │
│    sys,json;print(json.load(sys.stdin)['access_token'])") echo $TOKEN                                                │
│  • 你会看到 token 明显比之前短。                                                                                     │
│                                                                                                                      │
│  2 使用 token 调用 /auth/me 验证 JWT                                                                                 │
│                                                                                                                      │
│  • curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me                                              │
│  • 返回当前用户信息即成功。                                                                                          │
│                                                                                                                      │
│  3 如果你在 /docs 里验证                                                                                             │
│                                                                                                                      │
│  • /auth/login 仍采用 JSON 请求体，因此 Swagger 的 “Authorize” 按钮不会自动进行登录。你可以用 curl 或 Postman 获取   │
│    token 后，手动填入 Bearer token。                                                                                 │
│                                                                                                                      │
│ 关于 token 进一步缩短的说明                                                                                          │
│                                                                                                                      │
│  • 当前 token 已尽量精简。JWT 是带签名的，长度与签名算法（HS256）和 payload 长度相关。我们已经用 22 字符的 compact   │
│    UUID，并去掉了 email/role 等冗余信息。除非切换到非 JWT 的随机 opaque token（例如把 session                        │
│    存数据库/Redis，仅返回一个短 ID），否则进一步明显缩短空间有限。                                                   │
│  • 如果你确实希望极短的 token（例如 32-64 字符），可以改为 opaque token（服务端存状态）或改用                        │
│    Paseto/v4.local（对称加密）封装，但那会增加状态存储或引入新库。需要我可以给你方案与实现。                         │
│                                                                                                                      │
│ 后续建议                                                                                                             │
│                                                                                                                      │
│  • 现在还没有强制“认证 + 激活”保护到所有业务接口。如果你希望默认全站保护（除 /auth 与                                │
│    /health），我可以添加中间件/全局依赖。                                                                            │
│  • 实现激活码接口（/auth/activate）和管理员管理激活码的能力。                                                        │
│  • 初始化 Alembic 迁移，替代启动时建表，便于生产环境演进。                                                           │
│                                                                                                                      │
│ 我可以帮你：                                                                                                         │
│                                                                                                                      │
│  •  1 添加 /auth/activate 接口，并提供激活码生成/撤销的管理员端点                                                    │
│  •  2 为非 /auth 和 /health 的路由添加“认证+激活”强制校验                                                            │
│  •  3 准备 Alembic 迁移并生成初始 migration                                                                          │
│  •  4 生成一份操作与架构说明发到 Confluence，或创建 Jira 任务追踪“激活码实现与全站拦截”                              │
│                                                                                                                      │
│ 你希望我下一步做哪一个？                                                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

---


> 下面我们开始开发激活码部分，我先描述需求：
1. 激活码表为activation_codes, id:uuid 主键、activation_code:唯一键、user_email:
外键,关联accounts表的email、activation_status:激活状态（未激活/已激活/已过期）、expiry_date:text:过期时间、activation_ti
me:text:激活时间、valid_days:int:有效天数、create_time:text、update_time:text
2. 生成激活码接口，管理员可以使用此接口， 生成接口需要输入有效时间的天数，
生成的激活码的数量，生成后未使用前，生成一个32位的激活码、设置激活状态为未激活，有效时间填入输入的天数，创建时间也写入当
前时间，更新时间也写当前时间
3.
激活码激活接口，普通用户填入激活码，然后先查询激活码表是否存在，如果存在查询是否为未激活，如果未激活，就将激活码写入到ac
counts表的激活码activation_code，过期时间通过将激活码的有效时间加上当前的时间日期后的结果写入expired_time，同时配置激活
状态activation_status为已激活。
同时在activation_codes表中也要同步用户的email，更新activation_status为已激活，计算出过期时间expiry_date，写入激活时间act
ivation_time


╭─ Response ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 好的，激活码功能已经就绪。我已经为你添加了数据模型、服务与两个接口：                                                 │
│                                                                                                                      │
│  • POST /activation/generate 管理员生成激活码                                                                        │
│  • POST /activation/activate 普通用户使用激活码进行激活                                                              │
│                                                                                                                      │
│ 在开始测试前，小提示                                                                                                 │
│                                                                                                                      │
│  • 因为我们刚新增了 activation_codes 表，确保服务在更新代码后完成一次重启，应用会在启动时自动创建新表。              │
│  • 管理员权限：目前注册接口默认创建 role=user 的用户。请先把你要生成激活码的账号设置成管理员。                       │
│                                                                                                                      │
│ 如何把某个用户设为管理员                                                                                             │
│                                                                                                                      │
│  • 在 PostgreSQL 上执行（替换你的邮箱）： UPDATE accounts SET role='admin' WHERE email='admin@example.com';          │
│  • 验证： SELECT email, role FROM accounts WHERE email='admin@example.com';                                          │
│                                                                                                                      │
│ 测试步骤指南                                                                                                         │
│                                                                                                                      │
│  1 管理员登录，生成激活码                                                                                            │
│                                                                                                                      │
│  • 先用管理员账号登录拿到 token（已设置为 admin 的那一个）： curl -X POST "http://localhost:8000/auth/login" -H      │
│    "Content-Type: application/json" -d "{"email":"admin@example.com","password":"AdminPassword123!"}"                │
│  • 取出 access_token，调用生成接口（生成 5 个激活码，每个激活后有效 30 天）： curl -X POST                           │
│    "http://localhost:8000/activation/generate"                                                                       │
│    -H "Content-Type: application/json"                                                                               │
│    -H "Authorization: Bearer <ADMIN_TOKEN>"                                                                          │
│    -d "{"valid_days":30,"count":5}"                                                                                  │
│  • 返回示例（精简）： { "codes": [ { "id": "0c1e4a1e-....", "activation_code": "a3f0b4...32_chars...", "valid_days": │
│    30, "activation_status": "pending", "user_email": null, "expiry_date": null, "activation_time": null,             │
│    "create_time": "2025-09-10T08:30:00+00:00", "update_time": "2025-09-10T08:30:00+00:00" }, ... ] }                 │
│  • 你可以从返回中复制一个 activation_code 供下一步使用。                                                             │
│                                                                                                                      │
│  2 普通用户注册并登录                                                                                                │
│                                                                                                                      │
│  • 注册一个普通用户： curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" -d      │
│    "{"email":"user1@example.com","password":"Secret123!"}"                                                           │
│  • 登录： curl -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d                     │
│    "{"email":"user1@example.com","password":"Secret123!"}"                                                           │
│                                                                                                                      │
│  3 普通用户使用激活码激活                                                                                            │
│                                                                                                                      │
│  • 使用刚才生成的激活码： curl -X POST "http://localhost:8000/activation/activate"                                   │
│    -H "Content-Type: application/json"                                                                               │
│    -H "Authorization: Bearer <USER_TOKEN>"                                                                           │
│    -d "{"activation_code":"<复制的32位激活码>"}"                                                                     │
│  • 成功返回： { "email": "user1@example.com", "activation_status": "active", "expired_time":                         │
│    "2025-10-10T08:30:00+00:00" }                                                                                     │
│                                                                                                                      │
│  4 数据库侧验证（可选）                                                                                              │
│                                                                                                                      │
│  • 查看普通用户状态： SELECT email, activation_status, activation_code, expired_time FROM accounts WHERE             │
│    email='user1@example.com';                                                                                        │
│  • 查看激活码记录： SELECT activation_code, activation_status, user_email, activation_time, expiry_date FROM         │
│    activation_codes WHERE activation_code='<该码>';                                                                  │
│                                                                                                                      │
│ 接口行为说明                                                                                                         │
│                                                                                                                      │
│  • 生成激活码（管理员）                                                                                              │
│     • 输入 valid_days（激活后的有效天数）与 count（生成数量）                                                        │
│     • 每个激活码为 32 位十六进制字符串（secrets.token_hex(16)）                                                      │
│     • 初始状态为 pending（未激活），user_email/activation_time/expiry_date 为空                                      │
│     • create_time/update_time 为当前 UTC ISO 字符串                                                                  │
│  • 激活（普通用户）                                                                                                  │
│     • 校验激活码存在且状态为 pending                                                                                 │
│     • 更新 accounts：写入 activation_code、设置 activation_status=active、expired_time=当前时间+valid_days           │
│     • 更新 activation_codes：写入 user_email、设置                                                                   │
│       activation_status=active、activation_time=当前时间、expiry_date=当前时间+valid_days、update_time=当前时间      │
│  • 注意：未使用的激活码目前不会“自然过期”，仅在“激活后”根据 valid_days                                               │
│    计算有效期。如果你需要“激活码本身过期”（例如生成后 30                                                             │
│    天内未使用则失效），可以增加一个生成时的“码有效期”字段，并在激活时校验 create_time+期限                           │
│    是否已过。我可以按你的规则补上。                                                                                  │
│                                                                                                                      │
│ 常见问题                                                                                                             │
│                                                                                                                      │
│  • 403 Admin privilege required：表示当前 token 的用户不是管理员。请先把该用户的 role 改为 admin 再生成激活码。      │
│  • 400 Activation code not found / is not pending：激活码不存在或已被使用/已激活。                                   │
│  • 401 Unauthorized：Authorization 头未携带 Bearer token 或 token 无效/过期。                                        │
│  • 使用 Swagger 文档测试：/activation/* 需要在每次请求的 Authorize 中填入 Bearer token；/auth/login 仍为 JSON        │
│    请求体，不走 Swagger 的 OAuth2 表单流程。                                                                         │
│                                                                                                                      │
│ 下一步建议                                                                                                           │
│                                                                                                                      │
│  • 增加“列出激活码、撤销激活码”的管理员接口（将某码状态改为 revoked）。                                              │
│  • 对业务接口开启“认证+激活状态校验”的全站拦截（除 /auth 和 /health），确保未激活用户无法调用其他接口。              │
│  • 引入 Alembic 并生成迁移（accounts 和 activation_codes），避免生产环境仅靠启动时建表。                             │
│  • 增加业务审计：记录激活码使用日志、生成人与时间等。                                                                │
│                                                                                                                      │
│ 我可以帮你：                                                                                                         │
│                                                                                                                      │
│  • 创建 /activation/list 和 /activation/revoke 管理端接口                                                            │
│  • 给项目加“全站认证+激活”中间件                                                                                     │
│  • 初始化 Alembic 并生成迁移脚本                                                                                     │
│  • 为激活流程补充集成测试与使用文档（并可创建一个 PR）                                                               │
│                                                                                                                      │
│ 你希望我先实现管理员的“列出/撤销激活码”接口，还是先做全站拦截或 Alembic 迁移？                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

email: lishuo1607@gmail.com
key： eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJLOWVTRjF6WlNjZS1uS0I3V2RSTFFBIiwiaWF0IjoxNzU3NTA2OTY3LCJleHAiOjE3NTc1OTMzNjd9.4L4Fgp0XyR6fjjZkgPglTjIDeLEfsvJ78864bdOSJEE


email: lucida1607@gmail.com
key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaWpPN1AwZlRuYWlFUmxwSm1qUnJRIiwiaWF0IjoxNzU3NTA3NTM5LCJleHAiOjE3NTc1OTM5Mzl9.Uuv0iWwo0p-3O8rZF5Ozqq_qrj91e1UL5L5UYfD0Wmw

激活码：

{"codes":[
    {"id":"aa6abb24-7e0b-408f-9e6c-b4671a9400da","activation_code":"392b1f461828d99dcc9ab0c13d6827c1","valid_days":3,"activation_status":"pending","user_email":null,"expiry_date":null,"activation_time":null,"create_time":"2025-09-10T12:28:01.065282+00:00","update_time":"2025-09-10T12:28:01.065298+00:00"},{"id":"b540c76e-3f67-4ee2-82d7-9624347126d2","activation_code":"649e0faa610e3262295bac2920ddbec9","valid_days":3,"activation_status":"pending","user_email":null,"expiry_date":null,"activation_time":null,"create_time":"2025-09-10T12:28:01.065564+00:00","update_time":"2025-09-10T12:28:01.065573+00:00"},{"id":"f45e8a80-d19d-4388-8616-ae4dd4d27c65","activation_code":"e714f3431234bf72e6c597627dc3e1dc","valid_days":3,"activation_status":"pending","user_email":null,"expiry_date":null,"activation_time":null,"create_time":"2025-09-10T12:28:01.065675+00:00","update_time":"2025-09-10T12:28:01.065682+00:00"},{"id":"512ed8ff-521e-4ba8-8084-e8fd2b3339e8","activation_code":"9b018aecfbb4f072c1d67a63f079180f","valid_days":3,"activation_status":"pending","user_email":null,"expiry_date":null,"activation_time":null,"create_time":"2025-09-10T12:28:01.065762+00:00","update_time":"2025-09-10T12:28:01.065768+00:00"},{"id":"37b3096a-5d90-41e9-bfa5-1e646ed5e6a9","activation_code":"a9a85a9f9684313ebc9f3743f17c4aa8","valid_days":3,"activation_status":"pending","user_email":null,"expiry_date":null,"activation_time":null,"create_time":"2025-09-10T12:28:01.065833+00:00","update_time":"2025-09-10T12:28:01.065839+00:00"}]

}
