from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.data.schemas import User
from uuid import UUID

# Отримати одного користувача за id
async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_users_by_ids(db, ids: list):
    result = await db.execute(select(User).where(User.id.in_(ids)))
    return result.scalars().all()
