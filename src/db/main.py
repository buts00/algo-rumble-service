from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.testing.plugin.plugin_base import config
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator

from src.config import Config



async_engine = create_async_engine(url=Config.ALGO_RUMBLE_DB_URL)
judge0_async_engine = create_async_engine(url=Config.JUDGE0_DB_URL)


async def init_db() -> None:
    """
    Initializes the algo_rumble database.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def init_judge0_db() -> None:
    """
    Initializes the judge0 database.
    Use this if you have models specific to the judge0 database.
    """
    async with judge0_async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async session for the algo_rumble database.
    """
    async_session = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


async def get_judge0_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async session for the judge0 database.
    """
    async_session = async_sessionmaker(bind=judge0_async_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
