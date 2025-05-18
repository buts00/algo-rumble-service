import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, update
from uuid import UUID

from src.data.schemas import Match, MatchStatus, Problem, User
from src.presentation.websocket import manager
from src.business.services.match_rating import (
    update_ratings_after_match,
    update_ratings_for_draw,
)


async def select_problem_for_match(db, player1_rating: int, player2_rating: int):
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


async def send_match_notification(user_id: str, data):
    try:
        await manager.send_match_notification(user_id, data)
    except Exception:
        pass


async def cancel_expired_matches(db):
    try:
        expiry_time = datetime.utcnow() - timedelta(minutes=5)
        result = await db.execute(
            select(Match).where(
                Match.status == MatchStatus.PENDING,
                Match.start_time < expiry_time,
            )
        )
        pending_matches = result.scalars().all()
        for match in pending_matches:
            match.status = MatchStatus.CANCELLED
            match.end_time = datetime.utcnow()
            await send_match_notification(
                str(match.player1_id),
                {
                    "type": "match_cancelled",
                    "match_id": str(match.id),
                    "reason": "Match expired",
                },
            )
            await send_match_notification(
                str(match.player2_id),
                {
                    "type": "match_cancelled",
                    "match_id": str(match.id),
                    "reason": "Match expired",
                },
            )
            db.add(match)
        await db.commit()
    except Exception:
        pass


async def create_match_for_players(
        player1, player2, db, match_acceptance_timeout_cb=None, match_draw_timeout_cb=None
):
    try:
        problem_id = await select_problem_for_match(db, player1.rating, player2.rating)
        new_match = Match(
            player1_id=player1.user_id,
            player2_id=player2.user_id,
            problem_id=problem_id,
            status=MatchStatus.PENDING,
            start_time=datetime.utcnow(),
        )
        db.add(new_match)
        await db.commit()
        await db.refresh(new_match)
        result1 = await db.execute(select(User).where(User.id == player1.user_id))
        user1 = result1.scalar_one_or_none()
        result2 = await db.execute(select(User).where(User.id == player2.user_id))
        user2 = result2.scalar_one_or_none()
        await send_match_notification(
            str(player1.user_id),
            {
                "type": "match_found",
                "match_id": str(new_match.id),
                "opponent_username": user2.username if user2 else "",
                "problem_id": str(problem_id) if problem_id else None,
            },
        )
        await send_match_notification(
            str(player2.user_id),
            {
                "type": "match_found",
                "match_id": str(new_match.id),
                "opponent_username": user1.username if user1 else "",
                "problem_id": str(problem_id) if problem_id else None,
            },
        )
        if match_acceptance_timeout_cb:
            asyncio.create_task(match_acceptance_timeout_cb(str(new_match.id), db))
        if match_draw_timeout_cb:
            asyncio.create_task(match_draw_timeout_cb(str(new_match.id), db))
    except Exception:
        pass


async def fetch_players_and_validate(db, player1_id, player2_id):
    id1_str = str(player1_id) if isinstance(player1_id, UUID) else player1_id
    id2_str = str(player2_id) if isinstance(player2_id, UUID) else player2_id

    result1 = await db.execute(select(User).where(User.id == player1_id))
    result2 = await db.execute(select(User).where(User.id == player2_id))

    player1 = result1.scalar_one_or_none()
    player2 = result2.scalar_one_or_none()

    if not player1 or not player2:
        return None, None, id1_str, id2_str

    return player1, player2, id1_str, id2_str


async def update_ratings_after_match_db(db, winner_id, loser_id):
    winner, loser, winner_id_str, loser_id_str = await fetch_players_and_validate(
        db, winner_id, loser_id
    )
    if not winner or not loser:
        return 0, 0

    new_winner_rating, new_loser_rating = update_ratings_after_match(
        winner.rating, loser.rating, True
    )

    await db.execute(
        update(User)
        .where(User.id == winner.id)
        .values(rating=new_winner_rating)
        .execution_options(synchronize_session="fetch")
    )
    await db.execute(
        update(User)
        .where(User.id == loser.id)
        .values(rating=new_loser_rating)
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()
    return new_winner_rating, new_loser_rating


async def update_ratings_for_draw_db(db, player1_id, player2_id):
    player1, player2, id1_str, id2_str = await fetch_players_and_validate(
        db, player1_id, player2_id
    )
    if not player1 or not player2:
        return 0, 0

    new_rating1, new_rating2 = update_ratings_for_draw(player1.rating, player2.rating)
    await db.execute(
        update(User)
        .where(User.id == id1_str)
        .values(rating=new_rating1)
        .execution_options(synchronize_session="fetch")
    )
    await db.execute(
        update(User)
        .where(User.id == id2_str)
        .values(rating=new_rating2)
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()
    return new_rating1, new_rating2



async def get_match_by_id(db, match_id):
    result = await db.execute(select(Match).where(Match.id == match_id))
    return result.scalar_one_or_none()

async def finish_match_with_winner(db, match_id, winner_id):
    await db.execute(
        update(Match)
        .where(Match.id == match_id)
        .values(
            status=MatchStatus.COMPLETED,
            winner_id=winner_id,
            end_time=datetime.now()
        )
    )
    await db.commit()
