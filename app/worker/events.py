import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SendEvent:
    task_id: str
    project_name: str
    to: str
    subject: str
    status: str  # "sent" | "failed"
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, event: SendEvent) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # 丢弃，防止慢消费者拖垮系统


event_bus = EventBus()
