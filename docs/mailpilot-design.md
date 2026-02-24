# Mailpilot - 统一邮件发送服务设计方案

## 项目概述

Mailpilot 是一个轻量级、自托管的邮件发送服务，用于统一管理多个项目的邮件发送任务。各项目通过 REST API 提交发送请求，服务统一处理发送、重试、日志记录。

**核心目标：**

- 所有项目的邮件发送集中到一个服务管理，告别分散的 Celery worker
- 单进程部署，用 systemd 守护，运维成本极低
- 每个项目独立的 SMTP 配置和模板管理
- 可靠的异步发送、自动重试、完整的发送日志

## 技术选型

| 组件 | 选择 | 用途 |
|------|------|------|
| Web 框架 | FastAPI | API 接口 + 后台任务 |
| 异步发送 | asyncio + aiosmtplib | 异步 SMTP 邮件发送 |
| 模板引擎 | Jinja2 | 邮件模板渲染 |
| 主数据库 | PostgreSQL 16 | 项目配置、任务队列、发送日志、邮件模板 |

## 架构设计

```
┌─────────────────────────────────────────┐
│        mailpilot (单进程 FastAPI)         │
│                                         │
│  ┌─────────┐    ┌──────────────────┐    │
│  │ REST API │───→│ 写入 PG 任务表    │    │
│  └─────────┘    └──────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Background Worker (asyncio)    │    │
│  │  ├─ 从 PG 取任务 (SKIP LOCKED) │    │
│  │  ├─ Jinja2 渲染模板             │    │
│  │  ├─ aiosmtplib 异步发送         │    │
│  │  ├─ 失败自动重试（指数退避）      │    │
│  │  └─ 更新状态 / 写日志           │    │
│  └─────────────────────────────────┘    │
│                                         │
├─────────────────────────────────────────┤
│                  PG                     │
│       配置/任务/日志/模板                 │
└─────────────────────────────────────────┘
```

## 数据模型

### PostgreSQL

#### projects — 项目注册表

```sql
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    api_key     VARCHAR(64) NOT NULL UNIQUE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### smtp_configs — SMTP 配置表

```sql
CREATE TABLE smtp_configs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id),
    name        VARCHAR(100),           -- 配置别名，如 "主发送" "营销"
    host        VARCHAR(255) NOT NULL,
    port        INT NOT NULL DEFAULT 587,
    username    VARCHAR(255) NOT NULL,
    password    TEXT NOT NULL,           -- 加密存储
    use_tls     BOOLEAN DEFAULT TRUE,
    from_email  VARCHAR(255) NOT NULL,
    from_name   VARCHAR(100),
    max_per_hour INT DEFAULT 100,       -- 每小时发送上限
    is_default  BOOLEAN DEFAULT FALSE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### email_tasks — 邮件任务队列表

```sql
CREATE TABLE email_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    smtp_config_id  UUID REFERENCES smtp_configs(id),  -- 为空则用默认配置
    to_addrs        TEXT[] NOT NULL,
    cc_addrs        TEXT[],
    bcc_addrs       TEXT[],
    reply_to        VARCHAR(255),
    subject         TEXT NOT NULL,
    body_html       TEXT,
    body_text       TEXT,
    template_id     VARCHAR(100),       -- 模板名称
    template_vars   JSONB,              -- 模板变量
    attachments     JSONB,              -- 附件信息
    priority        INT DEFAULT 0,      -- 优先级，数字越大越优先
    status          VARCHAR(20) DEFAULT 'pending',
    -- 状态: pending / processing / sent / failed / retry / cancelled
    retry_count     INT DEFAULT 0,
    max_retries     INT DEFAULT 3,
    next_retry_at   TIMESTAMPTZ,
    error           TEXT,
    webhook_url     VARCHAR(500),       -- 发送结果回调地址
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    scheduled_at    TIMESTAMPTZ,        -- 定时发送
    processing_at   TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ
);

-- 用于 worker 拉取待处理任务
CREATE INDEX idx_tasks_pending
    ON email_tasks (priority DESC, created_at ASC)
    WHERE status IN ('pending', 'retry');

-- 用于查询发送日志
CREATE INDEX idx_tasks_project_status
    ON email_tasks (project_id, status, created_at DESC);
```

## API 设计

所有 API 通过 `X-API-Key` Header 认证，关联到具体项目。

### 邮件发送

```
POST /api/v1/send
```

直接发送（传入内容）：

```json
{
    "to": ["user@example.com"],
    "cc": [],
    "subject": "测试邮件",
    "body_html": "<h1>Hello</h1>",
    "body_text": "Hello",
    "priority": 0,
    "smtp_config": "config-name-or-id"
}
```

```
POST /api/v1/send/template
```

用模板发送（传模板名 + 变量）：

```json
{
    "to": ["user@example.com"],
    "template": "welcome_email",
    "variables": {
        "username": "张三",
        "app_name": "MyApp"
    }
}
```

返回：

```json
{
    "task_id": "uuid",
    "status": "pending"
}
```

### 任务查询

```
GET /api/v1/tasks/{task_id}           # 查询单个任务状态
GET /api/v1/tasks?status=failed&page=1  # 查询任务列表
POST /api/v1/tasks/{task_id}/cancel   # 取消待发送任务
POST /api/v1/tasks/{task_id}/retry    # 手动重试失败任务
```

### 模板管理

```
POST   /api/v1/templates              # 创建模板
GET    /api/v1/templates              # 列出模板
GET    /api/v1/templates/{name}       # 获取模板详情
PUT    /api/v1/templates/{name}       # 更新模板
DELETE /api/v1/templates/{name}       # 删除模板
POST   /api/v1/templates/{name}/preview  # 预览渲染结果
```

### 项目配置

```
GET    /api/v1/config/smtp            # 列出 SMTP 配置
POST   /api/v1/config/smtp            # 添加 SMTP 配置
PUT    /api/v1/config/smtp/{id}       # 更新 SMTP 配置
POST   /api/v1/config/smtp/{id}/test  # 测试 SMTP 连接
```

### 统计与监控

```
GET /api/v1/stats                     # 发送统计（今日/本周/本月）
GET /api/v1/health                    # 健康检查
```

## 核心逻辑

### 后台 Worker

利用 FastAPI 的 lifespan 启动后台 asyncio 任务，从 PostgreSQL 拉取待处理邮件：

```python
async def worker_loop(concurrency: int = 5):
    """后台 worker 主循环，支持并发处理"""
    semaphore = asyncio.Semaphore(concurrency)

    while True:
        async with semaphore:
            task = await fetch_next_task()
            if task:
                asyncio.create_task(process_task(task))
            else:
                await asyncio.sleep(1)
                # 或使用 PG LISTEN/NOTIFY 实现即时触发


async def fetch_next_task():
    """从 PG 取一条待处理任务（SKIP LOCKED 保证并发安全）"""
    return await db.fetchrow("""
        UPDATE email_tasks
        SET status = 'processing', processing_at = NOW()
        WHERE id = (
            SELECT id FROM email_tasks
            WHERE status IN ('pending', 'retry')
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
              AND (scheduled_at IS NULL OR scheduled_at <= NOW())
            ORDER BY priority DESC, created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING *
    """)


async def process_task(task):
    """处理单个发送任务"""
    try:
        # 1. 如果使用模板，从 PG 获取并渲染
        if task['template_id']:
            subject, body_html, body_text = await render_template(task)
        else:
            subject = task['subject']
            body_html = task['body_html']
            body_text = task['body_text']

        # 2. 检查频率限制（查询 PG 近 1 小时发送量）
        await check_rate_limit(task['smtp_config_id'])

        # 3. 获取 SMTP 配置并发送
        smtp_config = await get_smtp_config(task)
        await send_email(smtp_config, task['to_addrs'], subject, body_html, body_text)

        # 4. 标记成功
        await mark_sent(task['id'])

        # 5. 回调通知（如果配置了 webhook）
        if task['webhook_url']:
            await notify_webhook(task['webhook_url'], task['id'], 'sent')

    except Exception as e:
        await schedule_retry(task, str(e))
```

### 重试策略

```python
async def schedule_retry(task, error: str):
    """指数退避重试"""
    retry_count = task['retry_count'] + 1
    if retry_count > task['max_retries']:
        await db.execute("""
            UPDATE email_tasks
            SET status = 'failed', error = $2, retry_count = $3
            WHERE id = $1
        """, task['id'], error, retry_count)
    else:
        delay = min(60 * (2 ** retry_count), 3600)  # 最长 1 小时
        await db.execute("""
            UPDATE email_tasks
            SET status = 'retry',
                error = $2,
                retry_count = $3,
                next_retry_at = NOW() + INTERVAL '%s seconds'
            WHERE id = $1
        """, task['id'], error, retry_count)
```

### 频率控制（PostgreSQL）

```python
async def check_rate_limit(smtp_config_id: str):
    """查询近 1 小时发送量，防止超出 SMTP 服务商限制"""
    row = await db.fetchrow("""
        SELECT COUNT(*) AS cnt, sc.max_per_hour
        FROM email_tasks et
        JOIN smtp_configs sc ON sc.id = et.smtp_config_id
        WHERE et.smtp_config_id = $1
          AND et.sent_at > NOW() - INTERVAL '1 hour'
        GROUP BY sc.max_per_hour
    """, smtp_config_id)
    if row and row['cnt'] >= row['max_per_hour']:
        raise RateLimitExceeded(f"超过每小时 {row['max_per_hour']} 封限制")
```

## 项目结构

```
mailpilot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口 + lifespan
│   ├── config.py            # 全局配置
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py          # 依赖注入（认证、DB）
│   │   ├── send.py          # 发送相关 API
│   │   ├── tasks.py         # 任务查询 API
│   │   ├── templates.py     # 模板管理 API
│   │   ├── config.py        # 项目配置 API
│   │   └── stats.py         # 统计 API
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py          # API Key 认证
│   │   └── security.py      # 密码加密
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── loop.py          # Worker 主循环
│   │   ├── sender.py        # SMTP 发送逻辑
│   │   └── retry.py         # 重试策略
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py
│   │   ├── smtp_config.py
│   │   └── email_task.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── ...              # Pydantic 模型
│   ├── db/
│   │   ├── __init__.py
│   │   └── postgres.py      # PG 连接
│   └── templates/
│       └── engine.py        # Jinja2 模板渲染
├── migrations/               # Alembic 数据库迁移
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 部署方式

### systemd（推荐，最简单）

```ini
[Unit]
Description=Mailpilot Email Service
After=network.target postgresql.service

[Service]
Type=exec
User=mailpilot
WorkingDirectory=/opt/mailpilot
ExecStart=/opt/mailpilot/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Docker Compose

```yaml
version: "3.8"
services:
  mailpilot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
    restart: always
```

## 依赖清单

```
fastapi
uvicorn
asyncpg          # PostgreSQL 异步驱动
aiosmtplib       # 异步 SMTP
jinja2           # 模板渲染
pydantic         # 数据校验
cryptography     # SMTP 密码加密
alembic          # 数据库迁移
httpx            # Webhook 回调
```

## GitHub 项目信息

- **项目名:** `mailpilot`
- **简介:** A lightweight, self-hosted email delivery service for managing email tasks across multiple projects. Features per-project SMTP configuration, template management, async sending with automatic retries, and delivery tracking. Built with FastAPI, PostgreSQL, and asyncio.
