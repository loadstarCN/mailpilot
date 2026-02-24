# Mailpilot API 对接文档

## 概述

Mailpilot 是一个统一邮件发送服务，提供异步邮件队列、模板渲染、发送状态查询等能力。

- **Base URL**：`http://your-server:8000/api/v1`
- **认证方式**：所有接口均需在请求头中携带 `X-API-Key`
- **数据格式**：请求与响应均为 `application/json`
- **发送模式**：异步队列。提交后立即返回 `task_id`，实际发送由后台 Worker 处理

---

## 认证

每个项目有独立的 API Key，在管理界面的「项目」页面获取。

```
X-API-Key: your-api-key-here
```

API Key 与项目绑定，所有操作（发送、查询、模板管理）均在该项目的数据隔离范围内。

---

## 任务状态说明

| 状态 | 含义 |
|------|------|
| `pending` | 已入队，等待处理 |
| `processing` | Worker 正在处理 |
| `sent` | 发送成功 |
| `failed` | 已超过最大重试次数，最终失败 |
| `retry` | 发送失败，等待重试 |
| `cancelled` | 已取消 |

---

## 一、发送邮件

### 1.1 直接发送

**POST** `/send`

不使用模板，直接传入邮件内容。

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `to` | `string[]` | ✅ | 收件人列表，合法邮箱地址，1~50 个 |
| `subject` | `string` | ✅ | 邮件主题，最长 500 字符 |
| `body_html` | `string` | ⚠️ | HTML 正文（与 `body_text` 至少填一个），最大 512KB |
| `body_text` | `string` | ⚠️ | 纯文本正文，最大 512KB |
| `cc` | `string[]` | ❌ | 抄送列表，最多 50 个 |
| `bcc` | `string[]` | ❌ | 密送列表，最多 50 个 |
| `reply_to` | `string` | ❌ | 回复地址 |
| `priority` | `integer` | ❌ | 优先级，数字越大越优先，默认 `0`，范围 `0~100` |
| `max_retries` | `integer` | ❌ | 最大重试次数，默认 `3`，范围 `0~10` |
| `smtp_config` | `string` | ❌ | SMTP 配置的 UUID，不传则使用项目默认配置 |
| `webhook_url` | `string` | ❌ | 发送结果回调地址（必须为合法 HTTP/HTTPS URL），见「Webhook」章节 |
| `scheduled_at` | `string` | ❌ | 定时发送时间，ISO 8601 格式，如 `2026-03-01T09:00:00+08:00` |

**请求示例**

```json
{
  "to": ["user@example.com"],
  "cc": ["manager@example.com"],
  "subject": "您的订单已发货",
  "body_html": "<p>您好，您的订单 <b>#12345</b> 已发货。</p>",
  "body_text": "您好，您的订单 #12345 已发货。",
  "priority": 1,
  "webhook_url": "https://your-app.com/hooks/email-status"
}
```

**响应示例**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

---

### 1.2 模板发送

**POST** `/send/template`

使用预先在管理界面创建的邮件模板发送，模板支持 Jinja2 变量渲染。

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `to` | `string[]` | ✅ | 收件人列表，1~50 个 |
| `template` | `string` | ✅ | 模板名称（在管理界面查看） |
| `variables` | `object` | ❌ | 模板变量键值对，默认 `{}` |
| `cc` | `string[]` | ❌ | 抄送列表，最多 50 个 |
| `bcc` | `string[]` | ❌ | 密送列表，最多 50 个 |
| `reply_to` | `string` | ❌ | 回复地址 |
| `priority` | `integer` | ❌ | 优先级，默认 `0`，范围 `0~100` |
| `max_retries` | `integer` | ❌ | 最大重试次数，默认 `3`，范围 `0~10` |
| `smtp_config` | `string` | ❌ | SMTP 配置 UUID，不传则使用项目默认 |
| `webhook_url` | `string` | ❌ | 回调地址（必须为合法 HTTP/HTTPS URL） |
| `scheduled_at` | `string` | ❌ | 定时发送时间（ISO 8601） |

**请求示例**

```json
{
  "to": ["newuser@example.com"],
  "template": "registration_pending",
  "variables": {
    "username": "张三",
    "email": "newuser@example.com",
    "support_email": "support@goodsmart.com"
  }
}
```

**响应示例**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

---

## 二、任务管理

### 2.1 查询任务详情

**GET** `/tasks/{task_id}`

**响应示例**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "project_id": "...",
  "to_addrs": ["user@example.com"],
  "cc_addrs": null,
  "bcc_addrs": null,
  "subject": "您的订单已发货",
  "status": "sent",
  "priority": 0,
  "retry_count": 0,
  "max_retries": 3,
  "error": null,
  "created_at": "2026-02-24T10:00:00Z",
  "scheduled_at": null,
  "sent_at": "2026-02-24T10:00:03Z"
}
```

---

### 2.2 查询任务列表

**GET** `/tasks`

**查询参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | `string` | 按状态筛选：`pending` / `processing` / `sent` / `failed` / `retry` / `cancelled` |
| `page` | `integer` | 页码，默认 `1`，最小 `1` |
| `page_size` | `integer` | 每页数量，默认 `20`，范围 `1~100` |

**请求示例**

```
GET /api/v1/tasks?status=failed&page=1&page_size=20
```

**响应示例**

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### 2.3 取消任务

**POST** `/tasks/{task_id}/cancel`

只有 `pending` / `retry` 状态的任务可以取消。

**响应示例**

```json
{ "message": "任务已取消" }
```

---

### 2.4 手动重试

**POST** `/tasks/{task_id}/retry`

将 `failed` 状态的任务重新放入队列。

**响应示例**

```json
{ "message": "任务已重新加入队列" }
```

---

## 三、模板管理

模板在管理界面创建后，可通过 API 进行增删改查和预览。
**模板以 `name` 作为唯一标识**（同项目内唯一），发送时传 `template` 字段填写 name。

### 3.1 获取模板列表

**GET** `/templates`

**响应示例**

```json
[
  {
    "id": "...",
    "project_id": "...",
    "name": "registration_pending",
    "subject": "您的注册申请已收到",
    "body_html": "...",
    "body_text": "...",
    "variables": [],
    "description": "注册等待审批通知",
    "is_active": true,
    "created_at": "2026-02-24T10:00:00Z",
    "updated_at": null
  }
]
```

---

### 3.2 获取单个模板

**GET** `/templates/{name}`

---

### 3.3 创建模板

**POST** `/templates`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `string` | ✅ | 模板名称，同项目唯一，建议蛇形命名如 `welcome_email` |
| `subject` | `string` | ✅ | 邮件主题，支持 Jinja2 变量，如 `欢迎 {{ username }}` |
| `body_html` | `string` | ✅ | HTML 正文，支持 Jinja2 |
| `body_text` | `string` | ❌ | 纯文本正文 |
| `variables` | `array` | ❌ | 变量描述（仅文档用途） |
| `description` | `string` | ❌ | 模板说明 |

**请求示例**

```json
{
  "name": "order_shipped",
  "subject": "您的订单 {{ order_id }} 已发货",
  "body_html": "<p>您好 {{ username }}，您的订单已发货，快递单号：{{ tracking_no }}</p>",
  "description": "订单发货通知"
}
```

**响应**：返回完整模板对象，HTTP 201。

---

### 3.4 更新模板

**PUT** `/templates/{name}`

只传需要修改的字段（支持部分更新）。

**请求体（可选字段）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `subject` | `string` | 新主题 |
| `body_html` | `string` | 新 HTML 正文 |
| `body_text` | `string` | 新纯文本正文 |
| `variables` | `array` | 变量描述 |
| `description` | `string` | 说明 |
| `is_active` | `boolean` | 是否启用 |

---

### 3.5 删除模板

**DELETE** `/templates/{name}`

**响应示例**

```json
{ "message": "已删除" }
```

---

### 3.6 预览模板渲染结果

**POST** `/templates/{name}/preview`

传入变量，返回渲染后的实际内容，用于调试。

**请求体**

```json
{
  "variables": {
    "username": "张三",
    "order_id": "#12345"
  }
}
```

**响应示例**

```json
{
  "subject": "您的订单 #12345 已发货",
  "body_html": "<p>您好 张三，您的订单已发货，快递单号：...</p>",
  "body_text": null
}
```

---

## 四、统计与健康

### 4.1 发送统计

**GET** `/stats`

返回今日、本周、本月的发送数量、成功数、失败数。

**响应示例**

```json
{
  "today": { "total": 120, "success": 118, "failed": 2 },
  "week":  { "total": 850, "success": 840, "failed": 10 },
  "month": { "total": 3200, "success": 3180, "failed": 20 }
}
```

---

### 4.2 健康检查

**GET** `/health`

无需认证。用于监控系统存活探针。

**响应示例**

```json
{ "status": "ok" }
```

---

## 五、Webhook 回调

发送请求时传入 `webhook_url`，任务状态变更后系统会向该地址发送 POST 请求。

### 触发时机

| 触发条件 | `status` 值 | 说明 |
|---------|------------|------|
| 邮件发送成功 | `sent` | SMTP 服务器接受了邮件 |
| 达到最大重试次数仍失败 | `failed` | 已不再重试，最终失败 |

> 注意：`retry`（等待重试中）状态**不触发**回调，仅最终结果触发。

### 回调请求格式

Mailpilot 向 `webhook_url` 发送 **HTTP POST** 请求，`Content-Type: application/json`。

**成功示例**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "sent",
  "error": null
}
```

**失败示例**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Connection refused: mx.example.com:25"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | `string` | 任务 UUID |
| `status` | `string` | `sent`（成功）或 `failed`（最终失败） |
| `error` | `string \| null` | 失败原因，成功时为 `null` |

### 注意事项

- 回调超时为 **10 秒**，超时或失败后**不重试**，请确保接收端能快速响应（立即返回 200，异步处理业务逻辑）
- 如不需要实时回调，可改用轮询 `GET /tasks/{task_id}` 查询状态

### 接收端示例

#### Python（FastAPI）

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/hooks/email-status")
async def receive_webhook(request: Request):
    data = await request.json()
    task_id = data["task_id"]
    status  = data["status"]
    error   = data.get("error")

    if status == "sent":
        print(f"邮件 {task_id} 发送成功")
    elif status == "failed":
        print(f"邮件 {task_id} 发送失败：{error}")

    return {"ok": True}  # 必须返回 2xx，否则 Mailpilot 记录回调失败
```

#### Python（Flask）

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.post("/hooks/email-status")
def receive_webhook():
    data    = request.get_json()
    task_id = data["task_id"]
    status  = data["status"]
    error   = data.get("error")

    if status == "sent":
        print(f"邮件 {task_id} 发送成功")
    elif status == "failed":
        print(f"邮件 {task_id} 发送失败：{error}")

    return jsonify({"ok": True})
```

#### Node.js（Express）

```js
const express = require('express');
const app = express();
app.use(express.json());

app.post('/hooks/email-status', (req, res) => {
  const { task_id, status, error } = req.body;

  if (status === 'sent') {
    console.log(`邮件 ${task_id} 发送成功`);
  } else if (status === 'failed') {
    console.log(`邮件 ${task_id} 发送失败：${error}`);
  }

  res.json({ ok: true }); // 必须返回 2xx
});
```

---

## 六、错误响应

所有接口在出错时返回统一格式：

```json
{
  "detail": "错误描述"
}
```

| HTTP 状态码 | 含义 |
|------------|------|
| `400` | 请求参数错误（如 smtp_config 不是有效 UUID） |
| `401` | API Key 无效或缺失 |
| `404` | 资源不存在（模板、任务） |
| `422` | 请求体格式错误（字段类型不匹配等） |
| `500` | 服务器内部错误 |

---

## 七、完整调用示例

### Python

```python
import httpx

BASE_URL = "http://your-server:8000/api/v1"
API_KEY  = "your-api-key-here"

headers = {"X-API-Key": API_KEY}

# 模板发送
resp = httpx.post(
    f"{BASE_URL}/send/template",
    headers=headers,
    json={
        "to": ["user@example.com"],
        "template": "registration_pending",
        "variables": {
            "username": "张三",
            "email": "user@example.com",
            "support_email": "support@goodsmart.com",
        },
    },
)
task_id = resp.json()["task_id"]

# 查询结果
result = httpx.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
print(result.json()["status"])  # sent / failed / pending ...
```

### JavaScript / Node.js

```js
const BASE_URL = 'http://your-server:8000/api/v1';
const API_KEY  = 'your-api-key-here';

const headers = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json',
};

// 模板发送
const resp = await fetch(`${BASE_URL}/send/template`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    to: ['user@example.com'],
    template: 'registration_pending',
    variables: {
      username: '张三',
      email: 'user@example.com',
      support_email: 'support@goodsmart.com',
    },
  }),
});
const { task_id } = await resp.json();

// 查询状态
const status = await fetch(`${BASE_URL}/tasks/${task_id}`, { headers });
console.log(await status.json());
```

### curl

```bash
# 模板发送
curl -X POST http://your-server:8000/api/v1/send/template \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "template": "registration_pending",
    "variables": {
      "username": "张三",
      "email": "user@example.com",
      "support_email": "support@goodsmart.com"
    }
  }'

# 查询任务状态
curl http://your-server:8000/api/v1/tasks/{task_id} \
  -H "X-API-Key: your-api-key-here"
```

---

## 附录：当前可用模板

| 模板名称 | 用途 | 所需变量 |
|---------|------|---------|
| `registration_pending` | 注册申请已收到，等待审批 | `username`, `email`, `support_email` |
| `registration_approved` | 注册审批通过，账号已激活 | `username`, `login_url`, `support_email` |
