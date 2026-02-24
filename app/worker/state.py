import time


class WorkerState:
    def __init__(self):
        self.running: bool = False
        self.active_count: int = 0
        self.started_at: float | None = None

    @property
    def uptime_seconds(self) -> float:
        if self.started_at:
            return time.time() - self.started_at
        return 0


worker_state = WorkerState()
