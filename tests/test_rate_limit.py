"""
限流功能测试脚本

测试流程：
1. 启动线程化 fake SMTP 服务器 (127.0.0.1:1025)
2. 通过 API 创建一个 max_per_hour=2 的 SMTP 配置
3. 逐封发送 3 封邮件，每封等待处理完毕后再发下一封
4. 验证前 2 封成功发送，第 3 封因限流被拦截

用法: python tests/test_rate_limit.py
前提: mailpilot 服务已在 localhost:8000 运行
"""

import socketserver
import sys
import threading
import time

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "0db37b6aac21b482a3e5097d865deda4e4744e66448c3afca0cbefafac348a59"
HEADERS = {"X-API-Key": API_KEY}

FAKE_SMTP_HOST = "127.0.0.1"
FAKE_SMTP_PORT = 2525


# ── 线程化 Fake SMTP 服务器 ───────────────────────────────────

class SMTPRequestHandler(socketserver.StreamRequestHandler):
    """简单的 SMTP 协议处理器，接受所有邮件并丢弃"""

    def handle(self):
        try:
            self._send(b"220 fake.smtp ESMTP ready\r\n")

            while True:
                line = self.rfile.readline()
                if not line:
                    break
                text = line.decode(errors="replace").strip()
                if not text:
                    continue

                cmd = text.split()[0].upper()

                if cmd in ("EHLO", "HELO"):
                    self._send(b"250-fake.smtp\r\n")
                    self._send(b"250-AUTH LOGIN PLAIN\r\n")
                    self._send(b"250 OK\r\n")

                elif cmd == "AUTH":
                    rest = text.upper()[5:].strip()
                    if rest.startswith("LOGIN"):
                        self._send(b"334 VXNlcm5hbWU6\r\n")
                        self.rfile.readline()  # base64 username
                        self._send(b"334 UGFzc3dvcmQ6\r\n")
                        self.rfile.readline()  # base64 password
                    self._send(b"235 Authentication successful\r\n")

                elif cmd == "MAIL":
                    self._send(b"250 OK\r\n")

                elif cmd == "RCPT":
                    self._send(b"250 OK\r\n")

                elif cmd == "DATA":
                    self._send(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                    while True:
                        data_line = self.rfile.readline()
                        if data_line in (b".\r\n", b".\n"):
                            break
                    self.server.email_count += 1
                    count = self.server.email_count
                    print(f"  [Fake SMTP] 邮件已接收并丢弃 [共 {count} 封]")
                    self._send(f"250 OK: queued as fake-{count}\r\n".encode())

                elif cmd == "RSET":
                    self._send(b"250 OK\r\n")

                elif cmd == "NOOP":
                    self._send(b"250 OK\r\n")

                elif cmd == "QUIT":
                    self._send(b"221 Bye\r\n")
                    break

                else:
                    self._send(b"500 Unknown command\r\n")
        except Exception as e:
            print(f"  [Fake SMTP] 连接处理异常: {e}")

    def _send(self, data: bytes):
        self.wfile.write(data)
        self.wfile.flush()


class ThreadedSMTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    email_count = 0


# ── 测试步骤 ─────────────────────────────────────────────────

def create_smtp_config(client: httpx.Client) -> str:
    """创建一个 max_per_hour=2 的 SMTP 配置"""
    resp = client.post(
        f"{BASE_URL}/api/v1/config/smtp",
        headers=HEADERS,
        json={
            "name": "限流测试SMTP",
            "host": FAKE_SMTP_HOST,
            "port": FAKE_SMTP_PORT,
            "username": "test@example.com",
            "password": "test123",
            "use_tls": False,
            "use_ssl": False,
            "from_email": "test@example.com",
            "from_name": "限流测试",
            "max_per_hour": 2,
            "is_default": False,
        },
    )
    if resp.status_code != 201:
        print(f"  创建 SMTP 配置失败: {resp.status_code} {resp.text}")
        sys.exit(1)
    config = resp.json()
    config_id = config["id"]
    print(f"[2/5] SMTP 配置已创建: id={config_id}, max_per_hour=2")
    return config_id


def send_one(client: httpx.Client, smtp_config_id: str, index: int) -> str:
    """发送 1 封邮件，返回 task_id"""
    resp = client.post(
        f"{BASE_URL}/api/v1/send",
        headers=HEADERS,
        json={
            "to": [f"user{index}@example.com"],
            "subject": f"限流测试邮件 #{index}",
            "body_text": f"这是第 {index} 封测试邮件",
            "smtp_config": smtp_config_id,
        },
    )
    data = resp.json()
    task_id = data["task_id"]
    print(f"  邮件 #{index} 已提交: task_id={task_id}")
    return task_id


def wait_for_task(client: httpx.Client, task_id: str, max_wait: int = 30) -> dict:
    """等待单个任务处理完毕"""
    start = time.time()
    while time.time() - start < max_wait:
        resp = client.get(f"{BASE_URL}/api/v1/tasks/{task_id}", headers=HEADERS)
        task = resp.json()
        if task["status"] not in ("pending", "processing"):
            return task
        time.sleep(0.5)
    # 超时返回当前状态
    resp = client.get(f"{BASE_URL}/api/v1/tasks/{task_id}", headers=HEADERS)
    return resp.json()


def print_results(results: list[dict]):
    """打印并验证结果"""
    print(f"\n[5/5] 结果验证:")
    print("=" * 60)

    sent_count = 0
    rate_limited = False

    for i, task in enumerate(results, 1):
        status = task["status"]
        error = task.get("error") or ""
        to = task["to_addrs"][0] if task.get("to_addrs") else "?"
        icon = {"sent": "OK", "retry": "!!", "failed": "XX"}.get(status, "??")

        print(f"  [{icon}] 邮件 #{i}  →  {to}")
        print(f"       状态: {status}    重试: {task['retry_count']}/{task['max_retries']}")
        if error:
            print(f"       错误: {error}")

        if status == "sent":
            sent_count += 1
        if "限制" in error or "limit" in error.lower():
            rate_limited = True

    print("=" * 60)

    if sent_count == 2 and rate_limited:
        print("\n  [PASS] 限流功能正常！前 2 封发送成功，第 3 封被限流拦截。")
    elif sent_count == 3:
        print("\n  [FAIL] 限流未生效！3 封邮件全部发送成功。")
    elif sent_count < 2:
        print(f"\n  [WARN] 异常：只有 {sent_count} 封发送成功，请检查 SMTP 配置。")
    else:
        print(f"\n  [INFO] 部分结果：{sent_count} 封发送成功，限流标记: {rate_limited}")


def cleanup(client: httpx.Client, task_ids: list[str]):
    """取消仍在等待的任务"""
    for tid in task_ids:
        resp = client.get(f"{BASE_URL}/api/v1/tasks/{tid}", headers=HEADERS)
        task = resp.json()
        if task["status"] in ("pending", "retry"):
            client.post(f"{BASE_URL}/api/v1/tasks/{tid}/cancel", headers=HEADERS)


def main():
    print("=" * 60)
    print("  Mailpilot 限流功能测试")
    print("=" * 60)

    # 启动线程化 fake SMTP 服务器（避免 Windows asyncio 兼容问题）
    smtp_server = ThreadedSMTPServer((FAKE_SMTP_HOST, FAKE_SMTP_PORT), SMTPRequestHandler)
    smtp_thread = threading.Thread(target=smtp_server.serve_forever, daemon=True)
    smtp_thread.start()

    # 验证端口可达：完成一次完整 SMTP 握手确保服务器就绪
    import socket
    for attempt in range(10):
        try:
            s = socket.create_connection((FAKE_SMTP_HOST, FAKE_SMTP_PORT), timeout=2)
            greeting = s.recv(1024)
            if b"220" in greeting:
                s.sendall(b"QUIT\r\n")
                s.recv(1024)
                s.close()
                break
            s.close()
        except OSError:
            time.sleep(0.5)
    else:
        print("错误: Fake SMTP 无法连接，退出")
        smtp_server.shutdown()
        return
    time.sleep(0.5)  # 等待服务器处理完毕
    print(f"[1/5] Fake SMTP 服务器已启动 (线程模式): {FAKE_SMTP_HOST}:{FAKE_SMTP_PORT}")

    with httpx.Client(timeout=10) as client:
        # 检查服务是否可用
        try:
            resp = client.get(f"{BASE_URL}/api/v1/health")
            if resp.json().get("status") != "ok":
                raise Exception()
        except Exception:
            print("错误: Mailpilot 服务未运行，请先启动 uvicorn")
            smtp_server.shutdown()
            return

        # 创建限流 SMTP 配置
        smtp_config_id = create_smtp_config(client)

        results = []
        task_ids = []

        # 逐封发送，等每封处理完再发下一封，确保限流检查能看到已发送记录
        for i in range(1, 4):
            tid = send_one(client, smtp_config_id, i)
            task_ids.append(tid)
            print(f"  等待邮件 #{i} 处理...")
            result = wait_for_task(client, tid)
            results.append(result)
            print(f"  邮件 #{i} 状态: {result['status']}")

        print(f"[3/5] 共发送 3 封邮件")

        print_results(results)

        # 清理未完成任务
        cleanup(client, task_ids)

    # 停止 fake SMTP
    smtp_server.shutdown()
    print("\nFake SMTP 服务器已关闭")


if __name__ == "__main__":
    main()
