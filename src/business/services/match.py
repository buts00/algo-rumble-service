import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import logger
from src.data.schemas import Match, MatchStatus, Problem, User
from src.data.schemas.match_schemas import PlayerQueueEntry
from src.presentation.websocket import manager

# Create a module-specific logger
match_logger = logger.getChild("match")

# In-memory queue for matchmaking
player_queue: List[PlayerQueueEntry] = []


async def add_player_to_queue(user_id: uuid.UUID, rating: int) -> bool:
    """
    Add a player to the matchmaking queue.
    Returns True if added, False if already in queue.
    """
    # Check if user is already in the queue
    for entry in player_queue:
        if entry.user_id == user_id:
            match_logger.info(f"Player {user_id} is already in the queue.")
            return False

    # Create a queue entry
    entry = PlayerQueueEntry(
        user_id=user_id, rating=rating, timestamp=datetime.utcnow()
    )

    # Add to queue
    player_queue.append(entry)
    match_logger.info(
        f"Player {user_id} added to queue. Queue size: {len(player_queue)}"
    )
    return True


async def process_match_queue(
    db: Session, match_acceptance_timeout_cb=None, match_draw_timeout_cb=None
) -> None:
    """
    Process the matchmaking queue to create matches between players.

    Args:
        db: Database session
        match_acceptance_timeout_cb: Callback function for match acceptance timeout
        match_draw_timeout_cb: Callback function for match draw timeout
    """
    if len(player_queue) < 2:
        return

    match_logger.info(f"Processing match queue. Queue size: {len(player_queue)}")

    # Sort queue by timestamp (oldest first)
    player_queue.sort(key=lambda x: x.timestamp)

    # Process queue
    i = 0
    while i < len(player_queue) - 1:
        player1 = player_queue[i]

        # Find a suitable opponent
        best_match_idx = -1
        min_rating_diff = float("inf")

        for j in range(i + 1, len(player_queue)):
            player2 = player_queue[j]
            rating_diff = abs(player1.rating - player2.rating)

            # Find the player with the closest rating
            if rating_diff < min_rating_diff:
                min_rating_diff = rating_diff
                best_match_idx = j

        if best_match_idx != -1:
            player2 = player_queue[best_match_idx]

            # Create a match
            try:
                # Select a problem for the match
                problem_id = await select_problem_for_match(
                    db, player1.rating, player2.rating
                )

                # Create match in database
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

                match_logger.info(
                    f"Match created: {new_match.id} between players {player1.user_id} and {player2.user_id}"
                )

                # Get usernames
                result1 = await db.execute(
                    select(User).where(User.id == player1.user_id)
                )
                user1 = result1.scalar_one_or_none()
                result2 = await db.execute(
                    select(User).where(User.id == player2.user_id)
                )
                user2 = result2.scalar_one_or_none()

                # Notify both players with usernames
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

                # Start 15s timeout for match acceptance
                if match_acceptance_timeout_cb:
                    asyncio.create_task(
                        match_acceptance_timeout_cb(str(new_match.id), db)
                    )
                # Start 45-min timeout for draw
                if match_draw_timeout_cb:
                    asyncio.create_task(match_draw_timeout_cb(str(new_match.id), db))

                # Remove both players from queue
                player_queue.pop(best_match_idx)
                player_queue.pop(i)

            except Exception as e:
                match_logger.error(f"Error creating match: {str(e)}")
                i += 1
        else:
            i += 1


async def select_problem_for_match(
    db: Session, player1_rating: int, player2_rating: int
) -> Optional[uuid.UUID]:
    """
    Select a problem for a match based on player ratings.

    Args:
        db: Database session
        player1_rating: Rating of player 1
        player2_rating: Rating of player 2

    Returns:
        The ID of the selected problem, or None if no suitable problem is found
    """
    try:
        # Calculate target rating (average of both players)
        target_rating = (player1_rating + player2_rating) // 2

        # Find problems with rating close to target
        result = await db.execute(select(Problem).order_by(Problem.rating))
        problems = result.scalars().all()

        if not problems:
            match_logger.warning("No problems found in database")
            return None

        # Find the problem with the closest rating
        closest_problem = min(problems, key=lambda p: abs(p.rating - target_rating))

        match_logger.info(
            f"Selected problem {closest_problem.id} with rating {closest_problem.rating} "
            f"for match with target rating {target_rating}"
        )

        return closest_problem.id
    except Exception as e:
        match_logger.error(f"Error selecting problem: {str(e)}")
        return None


async def send_match_notification(user_id: str, data: Dict[str, Any]) -> None:
    """
    Send a match notification to a user.

    Args:
        user_id: The ID of the user to notify
        data: The notification data
    """
    try:
        # Send via WebSocket if user is connected
        await manager.send_match_notification(user_id, data)
        match_logger.debug(f"Notification sent to user {user_id}: {json.dumps(data)}")
    except Exception as e:
        match_logger.error(f"Error sending notification to user {user_id}: {str(e)}")


async def cancel_expired_matches(db: Session) -> None:
    """
    Cancel matches that have been pending for too long.

    Args:
        db: Database session
    """
    try:
        # Find matches that have been pending for more than 5 minutes
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

            # Notify both players
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
            match_logger.info(f"Cancelled expired match: {match.id}")

        await db.commit()
        match_logger.info(f"Cancelled {len(pending_matches)} expired matches")
    except Exception as e:
        match_logger.error(f"Error cancelling expired matches: {str(e)}")
