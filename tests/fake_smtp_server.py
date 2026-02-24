"""
假 SMTP 服务器 - 接受所有邮件并丢弃，用于压力测试。

用法:
    python fake_smtp_server.py           # 正常模式，立即接受
    python fake_smtp_server.py --slow 3  # 模拟慢 SMTP，DATA 阶段延迟 3 秒

监听: 127.0.0.1:1025

配合使用：
    1. 在管理界面添加一个 SMTP 配置，指向 127.0.0.1:1025，不勾选 TLS/SSL
    2. 将其设为默认（或在测试请求中通过 smtp_config 字段指定）
"""

import argparse
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("fake-smtp")

received_count = 0


async def handle_smtp(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    slow_seconds: float = 0,
) -> None:
    global received_count
    addr = writer.get_extra_info("peername")

    async def send(line: str) -> None:
        writer.write((line + "\r\n").encode())
        await writer.drain()

    async def recv() -> str:
        line = await reader.readline()
        return line.decode(errors="replace").strip()

    try:
        await send("220 fake.smtp ESMTP ready")

        while True:
            line = await recv()
            if not line:
                break

            cmd = line.upper().split()[0] if line else ""

            if cmd in ("EHLO", "HELO"):
                await send("250-fake.smtp")
                await send("250-AUTH LOGIN PLAIN")
                await send("250 OK")

            elif cmd == "AUTH":
                rest = line.upper()[5:].strip()
                if rest.startswith("LOGIN"):
                    # AUTH LOGIN: 两次 334 challenge
                    await send("334 VXNlcm5hbWU6")   # "Username:"
                    await recv()                       # base64 用户名
                    await send("334 UGFzc3dvcmQ6")   # "Password:"
                    await recv()                       # base64 密码
                else:
                    # AUTH PLAIN: 凭证在同一行或下一行
                    pass
                await send("235 Authentication successful")

            elif cmd == "MAIL":
                await send("250 OK")

            elif cmd == "RCPT":
                await send("250 OK")

            elif cmd == "DATA":
                await send("354 End data with <CR><LF>.<CR><LF>")
                # 读取邮件正文直到单独的 "."
                while True:
                    data_line = await reader.readline()
                    if data_line in (b".\r\n", b".\n"):
                        break
                if slow_seconds > 0:
                    logger.info("慢速模式：等待 %.1f 秒...", slow_seconds)
                    await asyncio.sleep(slow_seconds)
                received_count += 1
                logger.info("邮件已接受并丢弃 [共 %d 封] 来自 %s", received_count, addr)
                await send(f"250 OK: queued as fake-{received_count}")

            elif cmd == "RSET":
                await send("250 OK")

            elif cmd == "NOOP":
                await send("250 OK")

            elif cmd == "QUIT":
                await send("221 Bye")
                break

            else:
                logger.debug("未知命令: %s", line)
                await send("500 Unknown command")

    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        logger.error("连接异常 %s: %s", addr, e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def main(host: str, port: int, slow_seconds: float) -> None:
    def factory(reader, writer):
        return handle_smtp(reader, writer, slow_seconds=slow_seconds)

    server = await asyncio.start_server(factory, host, port)
    mode = f"慢速模式（{slow_seconds}s 延迟）" if slow_seconds > 0 else "正常模式"
    logger.info("假 SMTP 服务器启动 [%s]: %s:%d", mode, host, port)
    logger.info("所有邮件将被接受并丢弃，不实际发送")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="假 SMTP 服务器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--slow", type=float, default=0, metavar="SECONDS",
                        help="DATA 阶段延迟 N 秒，模拟慢 SMTP（默认 0）")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.slow))
