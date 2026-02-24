# Mailpilot

轻量级、自托管的统一邮件发送服务，用于集中管理多个项目的邮件发送任务。

## 功能特性

- **多项目支持** — 每个项目独立的 API Key 和 SMTP 配置
- **异步发送** — 基于 asyncio + aiosmtplib，全程非阻塞
- **自动重试** — 指数退避策略，支持配置最大重试次数
- **模板管理** — Jinja2 模板存储于 PostgreSQL，支持变量校验
- **发送频率限制** — 基于 PostgreSQL 查询实现每小时发送量控制
- **定时发送** — 提交任务时指定 `scheduled_at` 即可延迟发送
- **Webhook 回调** — 发送成功或失败后通知业务系统
- **单进程部署** — 一个 uvicorn 进程搞定所有工作，systemd 守护，运维成本极低

## 技术栈

| 组件 | 选择 |
|------|------|
| Web 框架 | FastAPI |
| 异步 SMTP | aiosmtplib |
| 模板引擎 | Jinja2 |
| 数据库 | PostgreSQL 16 |

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 16

### 安装

```bash
git clone git@github.com:loadstarCN/mailpilot.git
cd mailpilot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填写 DATABASE_URL 和 SECRET_KEY
```

### 初始化数据库

```bash
alembic upgrade head
```

### 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

生产部署（Nginx + PM2/systemd）参见 [docs/deployment.md](docs/deployment.md)。

## API 使用

所有请求需携带 `X-API-Key` 请求头。

### 直接发送邮件

```bash
curl -X POST http://localhost:8000/api/v1/send \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "subject": "你好",
    "body_html": "<p>Hello world</p>"
  }'
```

### 使用模板发送

```bash
curl -X POST http://localhost:8000/api/v1/send/template \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "template": "welcome_email",
    "variables": {"username": "张三", "app_name": "MyApp"}
  }'
```

### 查询任务状态

```bash
curl http://localhost:8000/api/v1/tasks/{task_id} \
  -H "X-API-Key: your-api-key"
```

## API 参考

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/send` | 直接发送邮件 |
| POST | `/api/v1/send/template` | 使用模板发送 |
| GET | `/api/v1/tasks/{id}` | 查询任务状态 |
| GET | `/api/v1/tasks` | 查询任务列表 |
| POST | `/api/v1/tasks/{id}/cancel` | 取消待发送任务 |
| POST | `/api/v1/tasks/{id}/retry` | 手动重试失败任务 |
| POST | `/api/v1/templates` | 创建模板 |
| GET | `/api/v1/templates` | 列出模板 |
| GET | `/api/v1/templates/{name}` | 获取模板详情 |
| PUT | `/api/v1/templates/{name}` | 更新模板 |
| DELETE | `/api/v1/templates/{name}` | 删除模板 |
| POST | `/api/v1/templates/{name}/preview` | 预览渲染结果 |
| GET | `/api/v1/config/smtp` | 列出 SMTP 配置 |
| POST | `/api/v1/config/smtp` | 添加 SMTP 配置 |
| PUT | `/api/v1/config/smtp/{id}` | 更新 SMTP 配置 |
| POST | `/api/v1/config/smtp/{id}/test` | 测试 SMTP 连接 |
| GET | `/api/v1/stats` | 发送统计 |
| GET | `/api/v1/health` | 健康检查 |

## 设计文档

详细架构设计和数据模型见 [docs/mailpilot-design.md](docs/mailpilot-design.md)。

## License

MIT
