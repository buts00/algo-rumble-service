from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas import Match, MatchStatus
from src.errors import ResourceNotFoundException


async def get_match_by_id(db: AsyncSession, match_id: UUID) -> Match:
    """Get a match by ID from the database."""
    result = await db.execute(select(Match).where(Match.id == match_id))
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


async def update_match(db: AsyncSession, match_id: UUID, update_data: dict) -> Match:
    """Update a match in the database."""
    match = await get_match_by_id(db, match_id)
    for key, value in update_data.items():
        if value is not None:
            setattr(match, key, value)
    await db.commit()
    await db.refresh(match)
    return match


async def finish_match_with_winner(db: AsyncSession, match_id: UUID, winner_id: UUID) -> Match:
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