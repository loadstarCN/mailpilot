# Mailpilot

A lightweight, self-hosted email delivery service for managing email tasks across multiple projects.

## Features

- **Multi-project support** — each project gets its own API key and SMTP configuration
- **Async sending** — built on asyncio + aiosmtplib, no blocking
- **Automatic retries** — exponential backoff, configurable max retries
- **Template management** — Jinja2 templates stored in PostgreSQL, with variable schema
- **Rate limiting** — per-SMTP-config hourly send limits enforced via PostgreSQL
- **Scheduled sending** — submit a task with `scheduled_at` to send later
- **Webhook callbacks** — get notified on delivery success or failure
- **Single process** — runs as one uvicorn process, managed by systemd; no separate workers

## Tech Stack

| Component | Choice |
|-----------|--------|
| Web framework | FastAPI |
| Async SMTP | aiosmtplib |
| Template engine | Jinja2 |
| Database | PostgreSQL 16 |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16

### Install

```bash
git clone https://github.com/yourname/mailpilot.git
cd mailpilot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit .env and set DATABASE_URL and SECRET_KEY
```

### Run database migrations

```bash
alembic upgrade head
```

### Start the service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with systemd — see [docs/mailpilot-design.md](docs/mailpilot-design.md#部署方式).

## API Usage

All requests require an `X-API-Key` header.

### Send an email

```bash
curl -X POST http://localhost:8000/api/v1/send \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "subject": "Hello",
    "body_html": "<p>Hello world</p>"
  }'
```

### Send with a template

```bash
curl -X POST http://localhost:8000/api/v1/send/template \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "template": "welcome_email",
    "variables": {"username": "Alice", "app_name": "MyApp"}
  }'
```

### Check task status

```bash
curl http://localhost:8000/api/v1/tasks/{task_id} \
  -H "X-API-Key: your-api-key"
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/send` | Send email directly |
| POST | `/api/v1/send/template` | Send using a template |
| GET | `/api/v1/tasks/{id}` | Get task status |
| GET | `/api/v1/tasks` | List tasks |
| POST | `/api/v1/tasks/{id}/cancel` | Cancel a pending task |
| POST | `/api/v1/tasks/{id}/retry` | Retry a failed task |
| POST | `/api/v1/templates` | Create template |
| GET | `/api/v1/templates` | List templates |
| GET | `/api/v1/templates/{name}` | Get template |
| PUT | `/api/v1/templates/{name}` | Update template |
| DELETE | `/api/v1/templates/{name}` | Delete template |
| POST | `/api/v1/templates/{name}/preview` | Preview rendered template |
| GET | `/api/v1/config/smtp` | List SMTP configs |
| POST | `/api/v1/config/smtp` | Add SMTP config |
| PUT | `/api/v1/config/smtp/{id}` | Update SMTP config |
| POST | `/api/v1/config/smtp/{id}/test` | Test SMTP connection |
| GET | `/api/v1/stats` | Delivery statistics |
| GET | `/api/v1/health` | Health check |

## Design

See [docs/mailpilot-design.md](docs/mailpilot-design.md) for the full architecture and data model.

## License

MIT
