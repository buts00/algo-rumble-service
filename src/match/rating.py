"""
Elo Rating System Implementation

This module provides functions for calculating and updating player ratings
using the Elo rating system.

The Elo rating system is a method for calculating the relative skill levels
of players in zero-sum games such as chess. It is named after its creator
Arpad Elo, a Hungarian-American physics professor.

Basic formula:
- New Rating = Old Rating + K * (Actual Score - Expected Score)
- Expected Score = 1 / (1 + 10^((Opponent Rating - Player Rating) / 400))
- K is a constant that determines how much the rating can change (typically 16-32)
"""

import logging
from typing import Tuple, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.model import User

logger = logging.getLogger(__name__)

# K-factor determines how much ratings can change after a single match
K_FACTOR = 32

# Default rating for new players
DEFAULT_RATING = 1000


def calculate_expected_score(player_rating: int, opponent_rating: int) -> float:
    """
    Calculate the expected score for a player against an opponent.

    Args:
        player_rating: The player's current rating
        opponent_rating: The opponent's current rating

    Returns:
        The expected score (between 0 and 1)
    """
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def calculate_new_rating(
    current_rating: int, expected_score: float, actual_score: float
) -> int:
    """
    Calculate the new rating for a player after a match.

    Args:
        current_rating: The player's current rating
        expected_score: The expected score calculated before the match
        actual_score: The actual score (1 for win, 0.5 for draw, 0 for loss)

    Returns:
        The new rating as an integer
    """
    new_rating = current_rating + K_FACTOR * (actual_score - expected_score)
    return round(new_rating)


async def update_ratings_after_match(
    db: AsyncSession, winner_id: Union[UUID, str], loser_id: Union[UUID, str]
) -> Tuple[int, int]:

    winner, loser, winner_id_str, loser_id_str = await fetch_players_and_validate(db, winner_id, loser_id)
    if not winner or not loser:
        return 0, 0

    winner_expected = calculate_expected_score(winner.rating, loser.rating)
    loser_expected = calculate_expected_score(loser.rating, winner.rating)

    new_winner_rating = calculate_new_rating(winner.rating, winner_expected, 1.0)
    new_loser_rating = calculate_new_rating(loser.rating, loser_expected, 0.0)

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

    logger.info(
        f"Updated ratings after match: Winner {winner_id_str} ({winner.rating} → {new_winner_rating}), "
        f"Loser {loser_id_str} ({loser.rating} → {new_loser_rating})"
    )

    return new_winner_rating, new_loser_rating


async def update_ratings_for_draw(
    db: AsyncSession, player1_id: Union[UUID, str], player2_id: Union[UUID, str]
) -> Tuple[int, int]:

    player1, player2, id1_str, id2_str = await fetch_players_and_validate(db, player1_id, player2_id)
    if not player1 or not player2:
        return 0, 0

    expected1 = calculate_expected_score(player1.rating, player2.rating)
    expected2 = calculate_expected_score(player2.rating, player1.rating)

    new_rating1 = calculate_new_rating(player1.rating, expected1, 0.5)
    new_rating2 = calculate_new_rating(player2.rating, expected2, 0.5)
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
    logger.info(
        f"Updated ratings after draw: Player1 {id1_str} ({player1.rating} → {new_rating1}), "
        f"Player2 {id2_str} ({player2.rating} → {new_rating2})"
    )

    return new_rating1, new_rating2



async def fetch_players_and_validate(db, winner_id, loser_id):
    winner_id_str = str(winner_id) if isinstance(winner_id, UUID) else winner_id
    loser_id_str = str(loser_id) if isinstance(loser_id, UUID) else loser_id

    winner_result = await db.execute(select(User).where(User.id == winner_id))
    loser_result = await db.execute(select(User).where(User.id == loser_id))

    winner = winner_result.scalar_one_or_none()
    loser = loser_result.scalar_one_or_none()

    if not winner or not loser:
        logger.error(
            f"Failed to update ratings: User not found (winner_id={winner_id}, loser_id={loser_id})"
        )
        return None, None, winner_id_str, loser_id_str

    return winner, loser, winner_id_str, loser_id_str