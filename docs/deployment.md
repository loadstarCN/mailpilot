# 部署指南

## 环境要求

- Ubuntu 22.04+
- Python 3.11+
- PostgreSQL 16（外部服务，需提前准备好连接信息）
- Nginx（已安装）
- PM2（已安装）

---

## 一、服务器初始化

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-distutils python3.11-dev build-essential
/usr/bin/python3.11 --version  # 确认 3.11.x
```

> 不修改系统默认 `python3` 指向，避免影响 apt 等系统工具。后续所有命令均使用完整路径 `/usr/bin/python3.11`。
> `python3.11-dev` 和 `build-essential` 用于编译 `cryptography` 等含 C 扩展的依赖包。

---

## 二、部署应用

```bash
# 创建应用目录
sudo mkdir -p /var/www/mailpilot
sudo chown $USER:$USER /var/www/mailpilot

# 上传代码至 /var/www/mailpilot/（包含 app/、templates/、static/、migrations/ 等目录）

# 安装依赖
cd /var/www/mailpilot
/usr/bin/python3.11 -m pip install .

# 配置环境变量
cp .env.example .env
nano .env  # 填写 DATABASE_URL、SECRET_KEY 等

# 运行数据库迁移（首次部署执行，用于建表）
/usr/bin/python3.11 -m alembic upgrade head
```

---

## 三、启动服务（PM2）

```bash
pm2 start "/usr/bin/python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8000" \
  --name mailpilot --cwd /var/www/mailpilot
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

---

## 四、Nginx 配置

创建 `/etc/nginx/sites-available/mailpilot`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

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
# 上传新代码至 /var/www/mailpilot/

# 服务器上执行
cd /var/www/mailpilot
/usr/bin/python3.11 -m pip install .           # 如有新依赖
/usr/bin/python3.11 -m alembic upgrade head    # 如有新迁移
pm2 restart mailpilot
```

---

## 七、查看日志

```bash
pm2 logs mailpilot
```
