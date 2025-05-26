from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.services.standing import get_standing_service
from src.config import logger
from src.data.repositories import get_session
from src.data.schemas.standing import StandingResponse
from src.errors import DatabaseException

# Create a module-specific logger
standing_logger = logger.getChild("standing")

router = APIRouter(tags=["standing"])


@router.get(
    "/standing",
    response_model=StandingResponse,
)
async def get_standing(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """
    Get users sorted by rating for the standing/leaderboard.

    Args:
        limit: Maximum number of users to return (default: 100, max: 1000)
        offset: Number of users to skip (default: 0)
        db: Database session

    Returns:
        List of users sorted by rating
    """
    standing_logger.info(f"Standing request with limit={limit}, offset={offset}")

    try:
        # Get standing
        standing = await get_standing_service(db, limit, offset)
        standing_logger.info(
            f"Standing request successful: {len(standing.users)} entries"
        )

        return standing
    except DatabaseException as e:
        raise e
    except Exception as e:
        standing_logger.error(f"Unexpected error during standing request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")
