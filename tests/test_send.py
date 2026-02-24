"""
发送测试邮件脚本 - 使用 registration_pending 模板
用法：python test_send.py
"""

import httpx

API_KEY = "0db37b6aac21b482a3e5097d865deda4e4744e66448c3afca0cbefafac348a59"
BASE_URL = "http://localhost:8000"

payload = {
    "to": ["kunyoo@gmail.com"],
    "template": "registration_pending",
    "variables": {
        "username": "张三",
        "email": "zhangsan@example.com",
        "support_email": "support@goodsmart.com",
    },
}

response = httpx.post(
    f"{BASE_URL}/api/v1/send/template",
    headers={"X-API-Key": API_KEY},
    json=payload,
)

print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")
