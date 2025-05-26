from typing import List
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.schemas import Match, MatchStatus, User, MatchHistoryEntry
from src.errors import DatabaseException

profile_logger = logger.getChild("profile")


async def get_user_match_history(
    db: AsyncSession, user_id: UUID4, limit: int = 10, offset: int = 0
) -> List[MatchHistoryEntry]:
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
        # Get completed matches for the user
        result = await db.execute(
            select(Match)
            .where(
                ((Match.player1_id == user_id) | (Match.player2_id == user_id)),
                Match.status == MatchStatus.COMPLETED,
                Match.winner_id.isnot(None),
            )
            .order_by(Match.end_time.desc())
            .offset(offset)
            .limit(limit)
        )
        matches = result.scalars().all()

        # Convert matches to match history entries
        match_history = []
        for match in matches:
            # Determine if the user won or lost
            is_winner = match.winner_id == user_id
            status = "win" if is_winner else "loss"

            # Get the enemy user ID
            enemy_id = (
                match.player2_id if match.player1_id == user_id else match.player1_id
            )

            # Get the enemy user
            enemy_result = await db.execute(select(User).where(User.id == enemy_id))
            enemy = enemy_result.scalar_one_or_none()

            if not enemy:
                profile_logger.warning(f"Enemy user not found: ID {enemy_id}")
                continue

            # Create match history entry
            # Get the user's old and new ratings from the match
            if match.player1_id == user_id:
                old_rating = match.player1_old_rating or enemy.rating
                new_rating = match.player1_new_rating or enemy.rating
            else:
                old_rating = match.player2_old_rating or enemy.rating
                new_rating = match.player2_new_rating or enemy.rating

            match_history.append(
                MatchHistoryEntry(
                    enemy_name=enemy.username,
                    status=status,
                    old_rating=old_rating,
                    new_rating=new_rating,
                    finished_at=match.end_time,
                )
            )

        return match_history
    except Exception as e:
        profile_logger.error(
            f"Error retrieving match history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(
            detail="Failed to retrieve match history due to database error"
        )
