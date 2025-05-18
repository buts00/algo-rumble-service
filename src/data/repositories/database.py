from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import Config

async_engine = create_async_engine(url=Config.ALGO_RUMBLE_DB_URL)


async def init_db() -> None:
    """
    Initializes the algo_rumble database.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async session for the algo_rumble database.
    """
    async_session = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session