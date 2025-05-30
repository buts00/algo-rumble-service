from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.handler.schemas import (
    MatchHistory,
    ContributionCalendar,
    RatingHistory,
    TopicStats,
)
from src.storage.repositories.profile import (
    get_user_match_history,
    get_user_contribution_calendar,
    get_user_rating_history,
    get_user_topic_stats,
)
from src.errors import DatabaseException, BadRequestException

# Create a module-specific logger
profile_logger = logger.getChild("profile")


async def get_user_match_history_service(
    db: AsyncSession, user_id: UUID4, limit: int = 10, offset: int = 0
) -> MatchHistory:
    """
    Get match history for a specific user.

    Args:
        db: Database session
        user_id: ID of the user to get match history for
        limit: Maximum number of matches to return
        offset: Number of matches to skip

    Returns:
        Match history storage including entries and total count
    """
    try:
        profile_logger.info(f"Getting match history for user {user_id}")
        match_history_entries, total_count = await get_user_match_history(
            db, user_id, limit, offset
        )
        profile_logger.info(
            f"Retrieved {len(match_history_entries)} match history entries for user {user_id} (total: {total_count})"
        )
        return MatchHistory(entries=match_history_entries, total=total_count)
    except Exception as e:
        profile_logger.error(
            f"Error retrieving match history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to retrieve match history")


async def get_user_contribution_calendar_service(
    db: AsyncSession, user_id: UUID4, year: int
) -> ContributionCalendar:
    """
    Get contribution calendar storage for a specific user for a given year.

    Args:
        db: Database session
        user_id: ID of the user to get contribution calendar for
        year: Year to get contribution calendar for

    Returns:
        Contribution calendar storage
    """
    try:
        profile_logger.info(
            f"Getting contribution calendar for user {user_id} for year {year}"
        )
        contribution_calendar = await get_user_contribution_calendar(db, user_id, year)
        profile_logger.info(
            f"Retrieved contribution calendar for user {user_id} for year {year} with {len(contribution_calendar.entries)} entries"
        )
        return contribution_calendar
    except BadRequestException as e:
        profile_logger.warning(
            f"Bad request when retrieving contribution calendar for user {user_id} for year {year}: {str(e)}"
        )
        raise e
    except Exception as e:
        profile_logger.error(
            f"Error retrieving contribution calendar for user {user_id} for year {year}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to retrieve contribution calendar")


async def get_user_rating_history_service(
    db: AsyncSession, user_id: UUID4
) -> RatingHistory:
    """
    Get rating history for a specific user, sorted from oldest to newest.

    Args:
        db: Database session
        user_id: ID of the user to get rating history for

    Returns:
        Rating history storage
    """
    try:
        profile_logger.info(f"Getting rating history for user {user_id}")
        rating_history = await get_user_rating_history(db, user_id)
        profile_logger.info(
            f"Retrieved rating history for user {user_id} with {len(rating_history.history)} entries"
        )
        return rating_history
    except BadRequestException as e:
        profile_logger.warning(
            f"Bad request when retrieving rating history for user {user_id}: {str(e)}"
        )
        raise e
    except Exception as e:
        profile_logger.error(
            f"Error retrieving rating history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to retrieve rating history")


async def get_user_topic_stats_service(
    db: AsyncSession, user_id: UUID4, limit: int = 5
) -> TopicStats:
    """
    Get statistics about the top topics where the user has won matches.

    Args:
        db: Database session
        user_id: ID of the user to get topic statistics for
        limit: Maximum number of topics to return (default: 5)

    Returns:
        Topic statistics storage
    """
    try:
        profile_logger.info(f"Getting topic statistics for user {user_id}")
        topic_stats = await get_user_topic_stats(db, user_id, limit)
        profile_logger.info(
            f"Retrieved {len(topic_stats.topics)} topic statistics for user {user_id}"
        )
        return topic_stats
    except BadRequestException as e:
        profile_logger.warning(
            f"Bad request when retrieving topic statistics for user {user_id}: {str(e)}"
        )
        raise e
    except Exception as e:
        profile_logger.error(
            f"Error retrieving topic statistics for user {user_id}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to retrieve topic statistics")
