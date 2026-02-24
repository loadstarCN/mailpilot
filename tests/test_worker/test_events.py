"""测试事件总线"""

import asyncio

import pytest

from app.worker.events import EventBus, SendEvent


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        queue = bus.subscribe()

        event = SendEvent(
            task_id="123",
            project_name="test",
            to="user@example.com",
            subject="测试",
            status="sent",
        )
        await bus.publish(event)

        received = queue.get_nowait()
        assert received.task_id == "123"
        assert received.status == "sent"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()

        event = SendEvent(
            task_id="456",
            project_name="test",
            to="a@b.com",
            subject="hi",
            status="failed",
            error="timeout",
        )
        await bus.publish(event)

        assert q1.get_nowait().task_id == "456"
        assert q2.get_nowait().task_id == "456"

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.unsubscribe(q)

        event = SendEvent(
            task_id="789",
            project_name="test",
            to="a@b.com",
            subject="hi",
            status="sent",
        )
        await bus.publish(event)

        assert q.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_is_safe(self):
        bus = EventBus()
        q = asyncio.Queue()
        bus.unsubscribe(q)  # 不应抛异常

    @pytest.mark.asyncio
    async def test_full_queue_does_not_block(self):
        """队列满时不阻塞，事件被丢弃"""
        bus = EventBus()
        q = bus.subscribe()  # maxsize=256

        # 填满队列
        for i in range(256):
            await bus.publish(SendEvent(
                task_id=str(i), project_name="t", to="a@b.com",
                subject="s", status="sent",
            ))

        # 再发一个不应阻塞
        await bus.publish(SendEvent(
            task_id="overflow", project_name="t", to="a@b.com",
            subject="s", status="sent",
        ))

        assert q.qsize() == 256

    @pytest.mark.asyncio
    async def test_send_event_default_timestamp(self):
        event = SendEvent(
            task_id="1", project_name="t", to="a@b.com",
            subject="s", status="sent",
        )
        assert event.timestamp is not None

    @pytest.mark.asyncio
    async def test_send_event_with_error(self):
        event = SendEvent(
            task_id="1", project_name="t", to="a@b.com",
            subject="s", status="failed", error="SMTP错误",
        )
        assert event.error == "SMTP错误"
