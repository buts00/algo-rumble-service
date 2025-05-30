from typing import List, Any, Coroutine, Sequence

from pydantic import UUID4
from sqlalchemy import select, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.errors import DatabaseException, ResourceNotFoundException
from src.storage.models import User

user_logger = logger.getChild("user")


async def get_user_by_id(db: AsyncSession, user_id: UUID4) -> User:
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


async def get_users_by_ids(db: AsyncSession, ids: List[UUID4]) -> Sequence[User]:
    """Get users by their IDs from the database."""
    try:
        result = await db.execute(select(User).where(User.id.in_(ids)))
        users = result.scalars().all()
        return users
    except Exception as e:
        user_logger.error(f"Error retrieving users {ids}: {str(e)}")
        raise DatabaseException(detail="Failed to retrieve users due to database error")
