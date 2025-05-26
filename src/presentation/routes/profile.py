import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.business.services.auth_dependency import get_current_user
from src.business.services.profile import get_user_match_history_service, get_user_contribution_calendar_service, get_user_rating_history_service, get_user_topic_stats_service
from src.config import logger
from src.data.repositories import get_session
from src.data.schemas import MatchHistoryEntry, UserBaseResponse, ContributionCalendar, RatingHistory, MatchHistory, TopicStats
from src.errors import BadRequestException, DatabaseException

# Create a module-specific logger
profile_logger = logger.getChild("profile")

router = APIRouter(tags=["profile"])


@router.get(
    "/users/{user_id}/profile/match-history",
    response_model=MatchHistory,
    response_model_exclude={"created_at", "updated_at"},
)
async def get_user_match_history(
    user_id: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    """
    Get match history for a specific user.

    Args:
        user_id: ID of the user to get match history for
        limit: Maximum number of matches to return (default: 10, max: 100)
        offset: Number of matches to skip (default: 0)

    Returns:
        List of match history entries
        :param user_id:
        :param limit:
        :param offset:
        :param db:
        :param current_user:
    """
    profile_logger.info(f"Match history request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            profile_logger.warning(
                f"Match history request failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Get match history
        match_history = await get_user_match_history_service(
            db, user_uuid, limit, offset
        )
        profile_logger.info(
            f"Match history request successful: {len(match_history.entries)} entries for user {user_id} (total: {match_history.total})"
        )

        return match_history
    except BadRequestException as e:
        raise e
    except DatabaseException as e:
        raise e
    except Exception as e:
        profile_logger.error(f"Unexpected error during match history request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")


@router.get(
    "/users/{user_id}/profile/activity-heatmap/{year}",
    response_model=ContributionCalendar,
)
async def get_user_contribution_calendar(
    user_id: str,
    year: int,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    """
    Get contribution calendar data for a specific user for a given year.

    Args:
        user_id: ID of the user to get contribution calendar for
        year: Year to get contribution calendar for

    Returns:
        Contribution calendar data
        :param user_id:
        :param year:
        :param db:
        :param current_user:
    """
    profile_logger.info(f"Contribution calendar request for user ID: {user_id}, year: {year}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            profile_logger.warning(
                f"Contribution calendar request failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Get contribution calendar
        contribution_calendar = await get_user_contribution_calendar_service(
            db, user_uuid, year
        )
        profile_logger.info(
            f"Contribution calendar request successful: {len(contribution_calendar.entries)} entries for user {user_id}, year {year}"
        )

        return contribution_calendar
    except BadRequestException as e:
        raise e
    except DatabaseException as e:
        raise e
    except Exception as e:
        profile_logger.error(f"Unexpected error during contribution calendar request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")


@router.get(
    "/users/{user_id}/profile/rating-history",
    response_model=RatingHistory,
)
async def get_user_rating_history(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    """
    Get rating history for a specific user, sorted from oldest to newest.

    Args:
        user_id: ID of the user to get rating history for

    Returns:
        Rating history data
        :param user_id:
        :param db:
        :param current_user:
    """
    profile_logger.info(f"Rating history request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            profile_logger.warning(
                f"Rating history request failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Get rating history
        rating_history = await get_user_rating_history_service(
            db, user_uuid
        )
        profile_logger.info(
            f"Rating history request successful: {len(rating_history.history)} entries for user {user_id}"
        )

        return rating_history
    except BadRequestException as e:
        raise e
    except DatabaseException as e:
        raise e
    except Exception as e:
        profile_logger.error(f"Unexpected error during rating history request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")


@router.get(
    "/users/{user_id}/profile/topic-stats",
    response_model=TopicStats,
)
async def get_user_topic_stats(
    user_id: str,
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    """
    Get statistics about the top topics where the user has won matches.
    This data can be used to create a polygon visualization of the user's strengths.

    Args:
        user_id: ID of the user to get topic statistics for
        limit: Maximum number of topics to return (default: 5, max: 10)

    Returns:
        Topic statistics data
        :param user_id:
        :param limit:
        :param db:
        :param current_user:
    """
    profile_logger.info(f"Topic statistics request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            profile_logger.warning(
                f"Topic statistics request failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Get topic statistics
        topic_stats = await get_user_topic_stats_service(
            db, user_uuid, limit
        )
        profile_logger.info(
            f"Topic statistics request successful: {len(topic_stats.topics)} entries for user {user_id}"
        )

        return topic_stats
    except BadRequestException as e:
        raise e
    except DatabaseException as e:
        raise e
    except Exception as e:
        profile_logger.error(f"Unexpected error during topic statistics request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")

