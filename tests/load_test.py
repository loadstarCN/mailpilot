"""
并发压力测试 - 验证 API 在高并发下能立即响应，不受 SMTP 速度影响。

准备步骤：
    1. 启动假 SMTP（模拟慢速 SMTP，3 秒延迟）:
       python fake_smtp_server.py --slow 3

    2. 在管理界面添加 SMTP 配置：
       主机: 127.0.0.1  端口: 1025  用户名/密码随意  不勾选 TLS/SSL  设为默认

    3. 运行压测:
       python load_test.py

预期结果：
    - API 响应时间应全部 < 500ms（只需 DB 写入，不等 SMTP）
    - 即使 SMTP 每封需要 3 秒，API 也应该立刻返回
"""

import asyncio
import statistics
import time

import httpx

# ── 配置区 ─────────────────────────────────────────────────────────────────
API_KEY = "0db37b6aac21b482a3e5097d865deda4e4744e66448c3afca0cbefafac348a59"
BASE_URL = "http://localhost:8000"

TOTAL = 100        # 总请求数
CONCURRENCY = 20   # 最大并发数
TIMEOUT = 10.0     # 单个请求超时（秒）

PAYLOAD_TEMPLATE = {
    "template": "registration_pending",
    "variables": {
        "username": "压测用户",
        "email": "loadtest@example.com",
        "support_email": "support@goodsmart.com",
    },
}
# ──────────────────────────────────────────────────────────────────────────


async def send_one(client: httpx.AsyncClient, idx: int) -> dict:
    payload = {
        **PAYLOAD_TEMPLATE,
        "to": [f"loadtest+{idx}@example.com"],
    }
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/api/v1/send/template",
            headers={"X-API-Key": API_KEY},
            json=payload,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000
        return {"ok": resp.status_code == 200, "ms": elapsed_ms, "status": resp.status_code}
    except Exception as e:
        elapsed_ms = (time.monotonic() - t0) * 1000
        return {"ok": False, "ms": elapsed_ms, "error": str(e)}


async def main() -> None:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results: list[dict] = []
    completed = 0

    async def limited_send(client: httpx.AsyncClient, idx: int) -> None:
        nonlocal completed
        async with semaphore:
            result = await send_one(client, idx)
            results.append(result)
            completed += 1
            mark = "✓" if result["ok"] else "✗"
            err = result.get("error", "")
            print(f"  [{idx:03d}] {mark} {result['ms']:6.1f}ms  {err}")

    print(f"压测配置: {TOTAL} 个请求，最大并发 {CONCURRENCY}，超时 {TIMEOUT}s")
    print(f"端点: POST {BASE_URL}/api/v1/send/template")
    print("-" * 55)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        t_start = time.monotonic()
        await asyncio.gather(*[limited_send(client, i) for i in range(TOTAL)])
        t_total = time.monotonic() - t_start

    # ── 统计 ──────────────────────────────────────────────────────────────
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]
    times = sorted(r["ms"] for r in ok)

    print("\n" + "=" * 55)
    print(f"总请求:   {TOTAL}")
    print(f"成功:     {len(ok)}  ({len(ok) / TOTAL * 100:.1f}%)")
    print(f"失败:     {len(fail)}")

    if times:
        p95 = times[int(len(times) * 0.95)]
        p99 = times[min(int(len(times) * 0.99), len(times) - 1)]
        print(f"\nAPI 响应时间（ms）:")
        print(f"  最小:    {min(times):.1f}")
        print(f"  最大:    {max(times):.1f}")
        print(f"  平均:    {statistics.mean(times):.1f}")
        print(f"  中位数:  {statistics.median(times):.1f}")
        print(f"  P95:     {p95:.1f}")
        print(f"  P99:     {p99:.1f}")

        if p99 < 500:
            verdict = "✓ PASS — API 响应时间正常，不受 SMTP 阻塞"
        else:
            verdict = "✗ FAIL — P99 超过 500ms，存在 DB 连接竞争或阻塞"
        print(f"\n结论: {verdict}")

    print(f"\n总耗时:   {t_total:.2f}s")
    print(f"吞吐量:   {TOTAL / t_total:.1f} req/s")

    if fail:
        print(f"\n失败详情（前 5 条）:")
        for r in fail[:5]:
            print(f"  {r}")


if __name__ == "__main__":
    asyncio.run(main())
