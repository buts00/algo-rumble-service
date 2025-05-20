import logging
from typing import Tuple, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas.user import User

logger = logging.getLogger(__name__)

# K-factor determines how much ratings can change after a single match
K_FACTOR = 32

# Default rating for new players
DEFAULT_RATING = 1000


class RatingService:
    @staticmethod
    def calculate_expected_score(player_rating: int, opponent_rating: int) -> float:
        """
        Calculate the expected score for a player against an opponent.
        """
        return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))

    @staticmethod
    def calculate_new_rating(
        current_rating: int, expected_score: float, actual_score: float
    ) -> int:
        """
        Calculate the new rating for a player after a match.
        """
        new_rating = current_rating + K_FACTOR * (actual_score - expected_score)
        return round(new_rating)

    @staticmethod
    async def update_ratings_after_match(
        db: AsyncSession, winner_id: Union[UUID, str], loser_id: Union[UUID, str]
    ) -> Tuple[int, int]:
        """
        Update ratings after a match using the Elo rating system.
        """
        winner, loser, winner_id_str, loser_id_str = (
            await RatingService.fetch_players_and_validate(db, winner_id, loser_id)
        )
        if not winner or not loser:
            return 0, 0

        winner_expected = RatingService.calculate_expected_score(
            winner.rating, loser.rating
        )
        loser_expected = RatingService.calculate_expected_score(
            loser.rating, winner.rating
        )

        new_winner_rating = RatingService.calculate_new_rating(
            winner.rating, winner_expected, 1.0
        )
        new_loser_rating = RatingService.calculate_new_rating(
            loser.rating, loser_expected, 0.0
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

        logger.info(
            f"Updated ratings after match: Winner {winner_id_str} ({winner.rating} → {new_winner_rating}), "
            f"Loser {loser_id_str} ({loser.rating} → {new_loser_rating})"
        )

        return new_winner_rating, new_loser_rating

    @staticmethod
    async def update_ratings_for_draw(
        db: AsyncSession, player1_id: Union[UUID, str], player2_id: Union[UUID, str]
    ) -> Tuple[int, int]:
        """
        Update ratings after a draw using the Elo rating system.
        """
        player1, player2, id1_str, id2_str = (
            await RatingService.fetch_players_and_validate(db, player1_id, player2_id)
        )
        if not player1 or not player2:
            return 0, 0

        expected1 = RatingService.calculate_expected_score(
            player1.rating, player2.rating
        )
        expected2 = RatingService.calculate_expected_score(
            player2.rating, player1.rating
        )

        new_rating1 = RatingService.calculate_new_rating(player1.rating, expected1, 0.5)
        new_rating2 = RatingService.calculate_new_rating(player2.rating, expected2, 0.5)
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

    @staticmethod
    async def fetch_players_and_validate(db, winner_id, loser_id):
        """
        Fetch players from the database and validate their existence.
        """
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
