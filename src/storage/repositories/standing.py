from typing import List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.errors import DatabaseException
from src.storage.models import User

standing_logger = logger.getChild("standing")


async def get_standing(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> Tuple[List[User], int]:
    """
    Get users sorted by rating for the standing/leaderboard.

    Args:
        db: Database session
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        Tuple containing list of users and total count
    """
    try:
        # Get total count
        count_query = select(func.count()).select_from(User)
        result = await db.execute(count_query)
        total = result.scalar_one()

        # Get users sorted by rating (descending)
        query = select(User).order_by(User.rating.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        users = result.scalars().all()

        standing_logger.info(
            f"Retrieved {len(users)} users for standing (total: {total})"
        )
        return users, total
    except Exception as e:
        standing_logger.error(f"Error retrieving standing: {str(e)}")
        raise DatabaseException(
            detail="Failed to retrieve standing due to database error"
        )
