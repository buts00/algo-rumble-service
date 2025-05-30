from datetime import datetime
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.errors import ResourceNotFoundException
from src.storage.models import Match, MatchStatus, Problem, User


async def get_match_by_id(db: AsyncSession, match_id: UUID4 | UUID | str) -> Match:
    """Get a match by ID from the database."""
    match_id_uuid = UUID(str(match_id))
    result = await db.execute(select(Match).where(Match.id == match_id_uuid))
    match = result.scalar_one_or_none()
    if not match:
        raise ResourceNotFoundException(detail="Match not found")
    return match


async def create_match(db: AsyncSession, match: Match) -> Match:
    """Create a new match in the database."""
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def update_match(db: AsyncSession, match_id: UUID4, update_data: dict) -> Match:
    """Update a match in the database."""
    match = await get_match_by_id(db, match_id)
    for key, value in update_data.items():
        if value is not None:
            setattr(match, key, value)
    await db.commit()
    await db.refresh(match)
    return match


async def finish_match_with_winner(
        db: AsyncSession, match_id: UUID4, winner_id: UUID4
) -> Match:
    """Finish a match with a winner."""
    match = await get_match_by_id(db, match_id)
    await db.execute(
        update(Match)
        .where(Match.id == match_id)
        .values(
            status=MatchStatus.COMPLETED,
            winner_id=winner_id,
            end_time=datetime.utcnow(),
        )
    )
    await db.commit()
    return match


async def select_problem_for_match(
        db: AsyncSession,
        player1_id: UUID4,
        player2_id: UUID4,
        player1_rating: int,
        player2_rating: int,
) -> UUID4 | None:
    """
    Select a problem for a match based on player ratings and unsolved problems.

    Args:
        db: Database session
        player1_id: ID of player 1
        player2_id: ID of player 2
        player1_rating: Rating of player 1
        player2_rating: Rating of player 2

    Returns:
        The ID of the selected problem, or None if no suitable problem is found
    """
    import random
    from sqlalchemy import not_, or_

    try:
        # Calculate target rating (average of both players)
        target_rating = (player1_rating + player2_rating) // 2

        # Get problems that both players have solved (from completed matches)
        player1_matches = await db.execute(
            select(Match).where(
                or_(Match.player1_id == player1_id, Match.player2_id == player1_id),
                Match.status == MatchStatus.COMPLETED,
                Match.problem_id.isnot(None),
            )
        )
        player1_problems = {
            match.problem_id for match in player1_matches.scalars().all()
        }

        player2_matches = await db.execute(
            select(Match).where(
                or_(Match.player1_id == player2_id, Match.player2_id == player2_id),
                Match.status == MatchStatus.COMPLETED,
                Match.problem_id.isnot(None),
            )
        )
        player2_problems = {
            match.problem_id for match in player2_matches.scalars().all()
        }

        # Combine the sets of solved problems
        solved_problems = player1_problems.union(player2_problems)

        # Find problems that neither player has solved
        if solved_problems:
            result = await db.execute(
                select(Problem)
                .where(not_(Problem.id.in_(solved_problems)))
                .order_by(Problem.rating)
            )
            unsolved_problems = result.scalars().all()
        else:
            # If no solved problems, get all problems
            result = await db.execute(select(Problem).order_by(Problem.rating))
            unsolved_problems = result.scalars().all()

        if not unsolved_problems:
            # If no unsolved problems, get all problems (fallback)
            result = await db.execute(select(Problem).order_by(Problem.rating))
            all_problems = result.scalars().all()

            if not all_problems:
                return None

            # Select a random problem as fallback
            return random.choice(all_problems).id

        # Find the problem with the closest rating to the target
        closest_problem = min(
            unsolved_problems, key=lambda p: abs(p.rating - target_rating)
        )
        return closest_problem.id

    except Exception as e:
        # Log the error
        from src.config import logger

        logger.error(f"Error selecting problem for match: {str(e)}")

        # Fallback: try to get any problem
        try:
            result = await db.execute(select(Problem))
            problems = result.scalars().all()
            if problems:
                return random.choice(problems).id
        except Exception:
            pass

        return None


async def get_expired_pending_matches(
        db: AsyncSession, expiry_time: datetime
) -> list[Match]:
    """Get all pending matches older than expiry_time."""
    result = await db.execute(
        select(Match).where(
            Match.status == MatchStatus.PENDING,
            Match.start_time < expiry_time,
        )
    )
    return result.scalars().all()


async def get_user_by_id(db: AsyncSession, user_id: UUID4) -> User | None:
    """Get a user by ID from the database."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_active_or_pending_match(db: AsyncSession, user_id: str) -> Match | None:
    """Get active or pending match for a user."""
    result = await db.execute(
        select(Match).where(
            (Match.player1_id == user_id) | (Match.player2_id == user_id),
            Match.status.in_([MatchStatus.ACTIVE, MatchStatus.PENDING]),
        )
    )
    return result.scalar_one_or_none()


async def get_match_history(
        db: AsyncSession, user_id: str, limit: int, offset: int
) -> list[Match]:
    """Get match history for a user."""
    result = await db.execute(
        select(Match)
        .where((Match.player1_id == user_id) | (Match.player2_id == user_id))
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def update_user_ratings(
        db: AsyncSession,
        user1_id: UUID4,
        user2_id: UUID4,
        user1_rating: int,
        user2_rating: int,
) -> None:
    """Update ratings for two users in the database."""
    await db.execute(
        update(User)
        .where(User.id == user1_id)
        .values(rating=user1_rating)
        .execution_options(synchronize_session="fetch")
    )
    await db.execute(
        update(User)
        .where(User.id == user2_id)
        .values(rating=user2_rating)
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()
