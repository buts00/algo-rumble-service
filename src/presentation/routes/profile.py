import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.business.services.auth_dependency import get_current_user
from src.business.services.profile import get_user_match_history_service
from src.config import logger
from src.data.repositories import get_session
from src.data.schemas import MatchHistoryEntry, UserBaseResponse
from src.errors import BadRequestException, DatabaseException

# Create a module-specific logger
profile_logger = logger.getChild("profile")

router = APIRouter(tags=["profile"])


@router.get(
    "/users/{user_id}/profile/match-history",
    response_model=List[MatchHistoryEntry],
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
            f"Match history request successful: {len(match_history)} entries for user {user_id}"
        )

        return match_history
    except BadRequestException as e:
        raise e
    except DatabaseException as e:
        raise e
    except Exception as e:
        profile_logger.error(f"Unexpected error during match history request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")
