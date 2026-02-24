"""
本地 Webhook 接收服务器，用于测试回调功能。
启动后监听 127.0.0.1:9000，收到回调时打印内容。
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            print(f"\n{'='*40}")
            print("收到 Webhook 回调:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"{'='*40}")
        except Exception as e:
            print(f"解析失败: {e}，原始内容: {body}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass  # 屏蔽默认访问日志


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 9000), WebhookHandler)
    print("Webhook 接收服务器已启动: http://127.0.0.1:9000")
    print("等待回调中...\n")
    server.serve_forever()
