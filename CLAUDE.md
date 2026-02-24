# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Mailpilot 是一个轻量级自托管统一邮件发送服务。详细设计见 `docs/mailpilot-design.md`。

## 技术栈

- **Python 3.11+**, **FastAPI**, **uvicorn**
- **PostgreSQL 16** + **SQLAlchemy 2.0 async** + **asyncpg**
- **aiosmtplib** 异步 SMTP 发送
- **Jinja2** 邮件模板渲染 + 管理界面 SSR
- **Tailwind CSS** (CDN) 管理界面样式
- **Chart.js** 监控图表
- **Alembic** 数据库迁移
- **itsdangerous** Session 签名
- **cryptography** (Fernet) SMTP 密码加密 / **bcrypt** 管理员密码哈希

## 常用命令

```bash
pip install -e .                                    # 安装依赖
alembic upgrade head                                # 运行迁移
uvicorn app.main:app --host 0.0.0.0 --port 8000    # 启动服务
pytest                                              # 运行测试
pytest tests/test_api/test_send.py -k "test_name"   # 运行单个测试
```

## 架构

**单进程设计** — 一个 uvicorn 进程同时运行 REST API、管理界面和后台 Worker。

### 代码分层

- `app/api/` — REST API（X-API-Key 认证），供外部项目调用。路由前缀 `/api/v1`
- `app/admin/` — 管理 Web 界面（Session/Cookie 认证），路由前缀 `/admin`
- `app/services/` — 业务逻辑层，API 和 Admin 共享（project, smtp, template, task, stats, admin）
- `app/core/` — 安全模块：API Key 认证 (`auth.py`)、加密 (`security.py`)、Session (`session.py`)
- `app/worker/` — 后台 Worker：主循环 (`loop.py`) 用 `FOR UPDATE SKIP LOCKED` 抢占任务；事件总线 (`events.py`) 为 SSE 推送提供数据
- `app/models/` — SQLAlchemy ORM：projects, smtp_configs, email_tasks, email_templates, admins
- `app/schemas/` — Pydantic v2 请求/响应模型
- `app/db/session.py` — async engine + sessionmaker
- `app/email_renderer/` — 从 DB 加载邮件模板并 Jinja2 渲染
- `templates/` — 管理界面 HTML 模板（Jinja2 SSR）
- `static/` — CSS/JS 静态资源

### 任务处理流程

API 接收请求 → 插入 `email_tasks` (pending) → Worker 轮询抢占 → 获取 SMTP 配置 → 渲染模板 → aiosmtplib 发送 → 更新状态 → 发布 SSE 事件 → Webhook 回调

### 双重认证

- **REST API**: `X-API-Key` Header → 关联 project，所有查询按 project 隔离
- **管理界面**: 管理员账号密码 → itsdangerous 签名 Cookie Session

## 环境变量

见 `.env.example`。DATABASE_URL 使用 `postgresql+asyncpg://` 前缀。首次启动自动创建默认管理员（`ADMIN_DEFAULT_USERNAME` / `ADMIN_DEFAULT_PASSWORD`）。

## 语言

README 和设计文档为中文，代码注释和 CLAUDE.md 使用中文。与用户交互使用中文。
