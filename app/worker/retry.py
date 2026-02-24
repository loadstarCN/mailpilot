from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.email_task import EmailTask


async def schedule_retry_or_fail(
    db: AsyncSession, task: EmailTask, error: str
) -> None:
    next_count = task.retry_count + 1
    if next_count > task.max_retries:
        task.status = "failed"
        task.error = error
        task.retry_count = next_count
    else:
        delay_seconds = min(60 * (2 ** next_count), 3600)
        task.status = "retry"
        task.error = error
        task.retry_count = next_count
        task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    await db.commit()
