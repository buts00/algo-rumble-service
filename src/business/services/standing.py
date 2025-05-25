from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories.standing import get_standing
from src.data.schemas.standing import StandingResponse, StandingEntry
from src.errors import DatabaseException

# Create a module-specific logger
standing_logger = logger.getChild("standing")


async def get_standing_service(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> StandingResponse:
    """
    Get users sorted by rating for the standing/leaderboard.

    Args:
        db: Database session
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        StandingResponse object containing users and total count
    """
    try:
        standing_logger.info(f"Getting standing with limit={limit}, offset={offset}")
        users, total = await get_standing(db, limit, offset)

        # Convert users to StandingEntry objects
        standing_entries = [
            StandingEntry(
                id=user.id,
                username=user.username,
                rating=user.rating,
                country_code=user.country_code,
            )
            for user in users
        ]

        standing_logger.info(f"Retrieved {len(standing_entries)} users for standing")
        return StandingResponse(users=standing_entries, total=total)
    except Exception as e:
        standing_logger.error(f"Error retrieving standing: {str(e)}")
        raise DatabaseException(detail="Failed to retrieve standing")
