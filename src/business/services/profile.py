from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories.profile import get_user_match_history
from src.data.schemas import MatchHistoryEntry
from src.errors import DatabaseException

# Create a module-specific logger
profile_logger = logger.getChild("profile")


async def get_user_match_history_service(
    db: AsyncSession, user_id: UUID4, limit: int = 10, offset: int = 0
) -> list[MatchHistoryEntry]:
    """
    Get match history for a specific user.

    Args:
        db: Database session
        user_id: ID of the user to get match history for
        limit: Maximum number of matches to return
        offset: Number of matches to skip

    Returns:
        List of match history entries
    """
    try:
        profile_logger.info(f"Getting match history for user {user_id}")
        match_history = await get_user_match_history(db, user_id, limit, offset)
        profile_logger.info(
            f"Retrieved {len(match_history)} match history entries for user {user_id}"
        )
        return match_history
    except Exception as e:
        profile_logger.error(
            f"Error retrieving match history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to retrieve match history")
