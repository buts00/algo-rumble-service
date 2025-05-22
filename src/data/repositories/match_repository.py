from datetime import datetime
from pydantic import UUID4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas import Match, MatchStatus, Problem, User
from src.errors import ResourceNotFoundException


async def get_match_by_id(db: AsyncSession, match_id: UUID4 | str) -> Match:
    """Get a match by ID from the database."""
    match_id_str = str(match_id)  # Convert to string for consistency
    result = await db.execute(select(Match).where(Match.id == match_id_str))
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
    db: AsyncSession, player1_rating: int, player2_rating: int
) -> UUID4 | None:
    """Select a problem for a match based on player ratings."""
    try:
        target_rating = (player1_rating + player2_rating) // 2
        result = await db.execute(select(Problem).order_by(Problem.rating))
        problems = result.scalars().all()
        if not problems:
            return None
        closest_problem = min(problems, key=lambda p: abs(p.rating - target_rating))
        return closest_problem.id
    except Exception:
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
    user2_rating: int
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