"""测试 Worker 重试策略"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.worker.retry import schedule_retry_or_fail
from tests.conftest import make_email_task


class TestScheduleRetryOrFail:
    @pytest.mark.asyncio
    async def test_retry_when_under_max(self):
        """重试次数未超限时，状态设为 retry"""
        task = make_email_task(retry_count=0, max_retries=3)
        db = AsyncMock()

        await schedule_retry_or_fail(db, task, "连接超时")

        assert task.status == "retry"
        assert task.retry_count == 1
        assert task.error == "连接超时"
        assert task.next_retry_at is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_when_exceeds_max(self):
        """重试次数超限时，状态设为 failed"""
        task = make_email_task(retry_count=3, max_retries=3)
        db = AsyncMock()

        await schedule_retry_or_fail(db, task, "SMTP 拒绝连接")

        assert task.status == "failed"
        assert task.retry_count == 4
        assert task.error == "SMTP 拒绝连接"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_delay_exponential_backoff(self):
        """验证指数退避延迟"""
        db = AsyncMock()
        now = datetime.now(timezone.utc)

        # 第 1 次重试: delay = min(60 * 2^1, 3600) = 120s
        task1 = make_email_task(retry_count=0, max_retries=5)
        await schedule_retry_or_fail(db, task1, "err")
        delay1 = (task1.next_retry_at - now).total_seconds()
        assert 115 < delay1 < 125  # 约 120 秒

        # 第 2 次重试: delay = min(60 * 2^2, 3600) = 240s
        task2 = make_email_task(retry_count=1, max_retries=5)
        await schedule_retry_or_fail(db, task2, "err")
        delay2 = (task2.next_retry_at - now).total_seconds()
        assert 235 < delay2 < 245  # 约 240 秒

        # 第 3 次重试: delay = min(60 * 2^3, 3600) = 480s
        task3 = make_email_task(retry_count=2, max_retries=5)
        await schedule_retry_or_fail(db, task3, "err")
        delay3 = (task3.next_retry_at - now).total_seconds()
        assert 475 < delay3 < 485  # 约 480 秒

    @pytest.mark.asyncio
    async def test_retry_delay_capped_at_3600(self):
        """延迟上限为 3600 秒"""
        task = make_email_task(retry_count=9, max_retries=20)
        db = AsyncMock()
        now = datetime.now(timezone.utc)

        await schedule_retry_or_fail(db, task, "err")

        delay = (task.next_retry_at - now).total_seconds()
        # min(60 * 2^10, 3600) = min(61440, 3600) = 3600
        assert 3595 < delay < 3605

    @pytest.mark.asyncio
    async def test_zero_max_retries_immediately_fails(self):
        """max_retries=0 时，第一次失败就变 failed"""
        task = make_email_task(retry_count=0, max_retries=0)
        db = AsyncMock()

        await schedule_retry_or_fail(db, task, "立即失败")

        assert task.status == "failed"
        assert task.retry_count == 1

    @pytest.mark.asyncio
    async def test_error_message_preserved(self):
        """错误信息正确保存"""
        task = make_email_task(retry_count=0, max_retries=3)
        db = AsyncMock()
        error_msg = "SMTPAuthenticationError: (535, b'Authentication failed')"

        await schedule_retry_or_fail(db, task, error_msg)

        assert task.error == error_msg
