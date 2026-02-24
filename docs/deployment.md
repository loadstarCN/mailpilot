# 部署指南

## 环境要求

- Ubuntu 20.04+
- Python 3.11+
- PostgreSQL 16
- Nginx
- PM2 或 systemd（进程管理二选一）

---

## 一、服务器初始化

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx postgresql
```

创建 PostgreSQL 数据库：

```bash
sudo -u postgres psql -c "CREATE USER mailpilot WITH PASSWORD 'your-db-password';"
sudo -u postgres psql -c "CREATE DATABASE mailpilot OWNER mailpilot;"
```

---

## 二、部署应用

```bash
# 创建应用目录
sudo mkdir -p /opt/mailpilot
sudo chown $USER:$USER /opt/mailpilot

# 上传代码（本地执行）
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  ./ user@server:/opt/mailpilot/

# 服务器上创建虚拟环境并安装依赖
cd /opt/mailpilot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 配置环境变量
cp .env.example .env
nano .env  # 填写 DATABASE_URL、SECRET_KEY 等

# 运行数据库迁移
alembic upgrade head
```

---

## 三、进程管理

### 方案 A：PM2（推荐，适合已有 PM2 环境）

创建 `ecosystem.config.js`：

```js
module.exports = {
  apps: [{
    name: 'mailpilot',
    script: '/opt/mailpilot/.venv/bin/uvicorn',
    args: 'app.main:app --host 127.0.0.1 --port 8000',
    cwd: '/opt/mailpilot',
    interpreter: 'none',
    env_file: '/opt/mailpilot/.env',
    restart_delay: 5000,
    max_restarts: 10,
    autorestart: true,
  }]
}
```

```bash
pm2 start ecosystem.config.js
pm2 save        # 保存进程列表
pm2 startup     # 生成开机自启命令，按提示执行输出的 sudo 命令
```

常用命令：

```bash
pm2 status
pm2 logs mailpilot
pm2 restart mailpilot
pm2 stop mailpilot
```

### 方案 B：systemd

创建 `/etc/systemd/system/mailpilot.service`：

```ini
[Unit]
Description=Mailpilot
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/opt/mailpilot
EnvironmentFile=/opt/mailpilot/.env
ExecStart=/opt/mailpilot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /opt/mailpilot
sudo systemctl daemon-reload
sudo systemctl enable --now mailpilot
sudo systemctl status mailpilot
```

---

## 四、Nginx 配置

创建 `/etc/nginx/sites-available/mailpilot`：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为实际域名或 IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE 长连接（监控页面实时推送）
    location /admin/monitoring/events {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/mailpilot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 五、HTTPS（可选，推荐）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 六、更新部署

```bash
# 上传新代码
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  ./ user@server:/opt/mailpilot/

# 服务器上执行
cd /opt/mailpilot
source .venv/bin/activate
pip install -e .           # 如有新依赖
alembic upgrade head       # 如有新迁移

# 重启服务
pm2 restart mailpilot      # PM2 方案
# 或
sudo systemctl restart mailpilot  # systemd 方案
```

---

## 七、查看日志

```bash
# PM2
pm2 logs mailpilot

# systemd
sudo journalctl -u mailpilot -f
```
