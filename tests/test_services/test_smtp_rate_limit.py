"""测试 SMTP 限流：每小时上限 + 每天上限（滚动 24 小时）"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.models.smtp_config import SmtpConfig
from app.services import smtp_service
from app.services.smtp_service import RateLimitExceeded, check_rate_limit
from tests.conftest import make_smtp_config

HOUR_SQL = "interval '1 hour'"
DAY_SQL = "interval '24 hours'"


def make_rate_db(config, *, hour=(0, None), day=(0, None)):
    """构造 mock session：db.get 返回配置，db.execute 按查询窗口返回 (已发送数量, 最早发送时间)

    执行过的 SQL（PostgreSQL 方言、参数内联）记录在 db.executed_sql，用于断言查询条件
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=config)
    db.executed_sql = []

    async def execute(stmt):
        sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        db.executed_sql.append(sql)
        result = MagicMock()
        result.one.return_value = day if DAY_SQL in sql else hour
        return result

    db.execute = execute
    return db


class TestDailyLimit:
    @pytest.mark.asyncio
    async def test_daily_limit_exceeded_raises(self):
        """近 24 小时已发送数达到每天上限时抛出，retry_after = 窗口内最早 sent_at + 24h + 5s"""
        config = make_smtp_config(max_per_hour=100, max_per_day=1000)
        earliest = datetime.now(timezone.utc) - timedelta(hours=20)
        db = make_rate_db(
            config,
            hour=(10, datetime.now(timezone.utc) - timedelta(minutes=10)),
            day=(1000, earliest),
        )

        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_rate_limit(db, config.id)

        exc = exc_info.value
        assert exc.window == "day"
        assert exc.limit == 1000
        assert str(exc) == "超过每天 1000 封限制"
        assert exc.retry_after == earliest + timedelta(hours=24, seconds=5)

    @pytest.mark.asyncio
    async def test_under_daily_limit_passes(self):
        """未达到每天上限时不抛出"""
        config = make_smtp_config(max_per_hour=100, max_per_day=1000)
        db = make_rate_db(
            config,
            hour=(10, datetime.now(timezone.utc) - timedelta(minutes=10)),
            day=(999, datetime.now(timezone.utc) - timedelta(hours=20)),
        )

        await check_rate_limit(db, config.id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_per_day", [None, 0])
    async def test_unlimited_daily_not_checked(self, max_per_day):
        """max_per_day 为 None / 0 表示不限：不抛出，也不执行 24 小时统计查询"""
        config = make_smtp_config(max_per_hour=100, max_per_day=max_per_day)
        db = make_rate_db(
            config,
            hour=(10, datetime.now(timezone.utc) - timedelta(minutes=10)),
            day=(100000, datetime.now(timezone.utc) - timedelta(hours=20)),
        )

        await check_rate_limit(db, config.id)

        assert len(db.executed_sql) == 1
        assert HOUR_SQL in db.executed_sql[0]

    @pytest.mark.asyncio
    async def test_both_exceeded_day_ends_later(self):
        """小时和天同时超限，天窗口结束更晚时按天抛出"""
        now = datetime.now(timezone.utc)
        hour_earliest = now - timedelta(minutes=30)  # 30 分钟后有空位
        day_earliest = now - timedelta(hours=10)  # 14 小时后有空位
        config = make_smtp_config(max_per_hour=100, max_per_day=1000)
        db = make_rate_db(config, hour=(100, hour_earliest), day=(1000, day_earliest))

        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_rate_limit(db, config.id)

        exc = exc_info.value
        assert exc.window == "day"
        assert exc.retry_after == day_earliest + timedelta(hours=24, seconds=5)

    @pytest.mark.asyncio
    async def test_both_exceeded_hour_ends_later(self):
        """小时和天同时超限，小时窗口结束更晚时按小时抛出"""
        now = datetime.now(timezone.utc)
        hour_earliest = now - timedelta(minutes=30)  # 30 分钟后有空位
        day_earliest = now - timedelta(hours=23, minutes=59)  # 1 分钟后有空位
        config = make_smtp_config(max_per_hour=100, max_per_day=1000)
        db = make_rate_db(config, hour=(100, hour_earliest), day=(1000, day_earliest))

        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_rate_limit(db, config.id)

        exc = exc_info.value
        assert exc.window == "hour"
        assert exc.limit == 100
        assert exc.retry_after == hour_earliest + timedelta(hours=1, seconds=5)

    @pytest.mark.asyncio
    async def test_counts_only_sent_status(self):
        """两个窗口的统计都只算 status='sent' 的任务"""
        config = make_smtp_config(max_per_day=1000)
        db = make_rate_db(config)

        await check_rate_limit(db, config.id)

        assert len(db.executed_sql) == 2
        for sql in db.executed_sql:
            assert "email_tasks.status = 'sent'" in sql
        assert any(HOUR_SQL in sql for sql in db.executed_sql)
        assert any(DAY_SQL in sql for sql in db.executed_sql)

    @pytest.mark.asyncio
    async def test_counts_only_this_smtp_config(self):
        """两个窗口的统计都只算当前 smtp_config 的任务"""
        config = make_smtp_config(max_per_day=1000)
        db = make_rate_db(config)

        await check_rate_limit(db, config.id)

        db.get.assert_awaited_once_with(SmtpConfig, config.id)
        assert len(db.executed_sql) == 2
        for sql in db.executed_sql:
            assert f"email_tasks.smtp_config_id = '{config.id}'" in sql


class TestHourlyLimit:
    @pytest.mark.asyncio
    async def test_hourly_limit_exceeded_raises(self):
        """原有每小时限流行为不变"""
        config = make_smtp_config(max_per_hour=100)
        earliest = datetime.now(timezone.utc) - timedelta(minutes=40)
        db = make_rate_db(config, hour=(100, earliest))

        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_rate_limit(db, config.id)

        exc = exc_info.value
        assert exc.window == "hour"
        assert str(exc) == "超过每小时 100 封限制"
        assert exc.retry_after == earliest + timedelta(hours=1, seconds=5)

    @pytest.mark.asyncio
    async def test_no_sent_tasks_passes(self):
        """窗口内没有已发送任务时不抛出"""
        config = make_smtp_config(max_per_hour=100, max_per_day=1000)
        db = make_rate_db(config)

        await check_rate_limit(db, config.id)

    @pytest.mark.asyncio
    async def test_naive_sent_at_gets_utc(self):
        """sent_at 不带时区时 retry_after 补上 UTC"""
        config = make_smtp_config(max_per_hour=100)
        earliest = datetime(2026, 10, 15, 1, 0, 0)
        db = make_rate_db(config, hour=(100, earliest))

        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_rate_limit(db, config.id)

        assert exc_info.value.retry_after == datetime(2026, 10, 15, 2, 0, 5, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_missing_config_passes(self):
        """配置不存在时不限流（与原逻辑一致）"""
        db = make_rate_db(None)

        await check_rate_limit(db, "missing-id")

        assert db.executed_sql == []


class TestRateLimitExceeded:
    def test_default_window_is_hour(self):
        """沿用旧的位置参数调用方式时默认是每小时"""
        retry_after = datetime.now(timezone.utc)
        exc = RateLimitExceeded(100, retry_after)
        assert exc.window == "hour"
        assert exc.retry_after == retry_after
        assert str(exc) == "超过每小时 100 封限制"


class TestSmtpConfigMaxPerDay:
    @pytest.mark.asyncio
    async def test_create_saves_max_per_day(self, mock_db):
        config = await smtp_service.create_smtp_config(
            mock_db,
            make_smtp_config().project_id,
            name="群发",
            host="smtp.example.com",
            port=465,
            username="user@example.com",
            password="secret",
            from_email="noreply@example.com",
            max_per_day=800,
        )

        assert config.max_per_day == 800
        mock_db.add.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_create_defaults_to_unlimited(self, mock_db):
        config = await smtp_service.create_smtp_config(
            mock_db,
            make_smtp_config().project_id,
            name=None,
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="secret",
            from_email="noreply@example.com",
        )

        assert config.max_per_day is None

    @pytest.mark.asyncio
    async def test_update_none_clears_max_per_day(self, mock_db):
        """max_per_day 显式传 None 写入（改为不限），其他字段的 None 仍表示不修改"""
        config = make_smtp_config(name="主发送", max_per_day=1000)
        mock_db.get = AsyncMock(return_value=config)

        await smtp_service.update_smtp_config(mock_db, config.id, name=None, max_per_day=None)

        assert config.max_per_day is None
        assert config.name == "主发送"

    @pytest.mark.asyncio
    async def test_update_sets_max_per_day(self, mock_db):
        config = make_smtp_config(max_per_day=None)
        mock_db.get = AsyncMock(return_value=config)

        await smtp_service.update_smtp_config(mock_db, config.id, max_per_day=1000)

        assert config.max_per_day == 1000

    @pytest.mark.asyncio
    async def test_update_without_key_keeps_max_per_day(self, mock_db):
        config = make_smtp_config(max_per_day=1000)
        mock_db.get = AsyncMock(return_value=config)

        await smtp_service.update_smtp_config(mock_db, config.id, max_per_hour=50)

        assert config.max_per_day == 1000
        assert config.max_per_hour == 50
