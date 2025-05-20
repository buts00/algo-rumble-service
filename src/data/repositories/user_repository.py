from uuid import UUID
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas import User
from src.errors import ResourceNotFoundException, DatabaseException
from src.config import logger

user_logger = logger.getChild("user")


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User:
    """Get a user by ID from the database."""
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user_logger.warning(f"User not found: ID {user_id}")
            raise ResourceNotFoundException(detail="User not found")
        return user
    except Exception as e:
        user_logger.error(f"Error retrieving user {user_id}: {str(e)}")
        raise DatabaseException(detail="Failed to retrieve user due to database error")


async def get_users_by_ids(db: AsyncSession, ids: List[UUID]) -> List[User]:
    """Get users by their IDs from the database."""
    try:
        result = await db.execute(select(User).where(User.id.in_(ids)))
        users = result.scalars().all()
        return users
    except Exception as e:
        user_logger.error(f"Error retrieving users {ids}: {str(e)}")
        raise DatabaseException(detail="Failed to retrieve users due to database error")