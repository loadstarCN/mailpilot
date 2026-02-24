from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str) -> None:
    global engine, async_session_maker
    engine = create_async_engine(database_url, pool_size=10, max_overflow=20)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_db() -> None:
    global engine, async_session_maker
    if engine:
        await engine.dispose()
        engine = None
        async_session_maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    assert async_session_maker is not None, "Database not initialized"
    async with async_session_maker() as session:
        yield session
