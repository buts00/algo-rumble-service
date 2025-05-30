import logging
import uuid
from typing import Tuple, Union, Optional
from pydantic import UUID4

from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Match, User
from src.storage.repositories.match_repository import update_user_ratings

logger = logging.getLogger(__name__)

# K-factor determines how much ratings can change after a single match
K_FACTOR = 32

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
    async def update_ratings(
        db: AsyncSession,
        player1_id: Union[UUID4, str],
        player2_id: Union[UUID4, str],
        player1_actual_score: float,
        player2_actual_score: float,
        log_context: str,
        player1_label: str,
        player2_label: str,
        match: Optional[Match] = None,
    ) -> Tuple[int, int]:
        """
        Update ratings for two players based on their actual scores.
        """

        (
            player1,
            player2,
            player1_id_str,
            player2_id_str,
        ) = await RatingService.fetch_players_and_validate(db, player1_id, player2_id)
        if not player1 or not player2:
            return 0, 0

        player1_expected = RatingService.calculate_expected_score(
            player1.rating, player2.rating
        )
        player2_expected = RatingService.calculate_expected_score(
            player2.rating, player1.rating
        )

        old_player1_rating = player1.rating
        old_player2_rating = player2.rating

        new_player1_rating = RatingService.calculate_new_rating(
            player1.rating, player1_expected, player1_actual_score
        )
        new_player2_rating = RatingService.calculate_new_rating(
            player2.rating, player2_expected, player2_actual_score
        )

        await update_user_ratings(
            db, player1.id, player2.id, new_player1_rating, new_player2_rating
        )

        if match:
            from src.storage.repositories.match_repository import update_match

            update_data = {
                "player1_old_rating": (
                    old_player1_rating
                    if match.player1_id == player1.id
                    else old_player2_rating
                ),
                "player2_old_rating": (
                    old_player2_rating
                    if match.player2_id == player2.id
                    else old_player1_rating
                ),
                "player1_new_rating": (
                    new_player1_rating
                    if match.player1_id == player1.id
                    else new_player2_rating
                ),
                "player2_new_rating": (
                    new_player2_rating
                    if match.player2_id == player2.id
                    else new_player1_rating
                ),
            }

            await update_match(db, match.id, update_data)

        logger.info(
            f"Updated ratings after {log_context}: "
            f"{player1_label} {player1_id_str} ({old_player1_rating} → {new_player1_rating}), "
            f"{player2_label} {player2_id_str} ({old_player2_rating} → {new_player2_rating})"
        )

        return new_player1_rating, new_player2_rating

    @staticmethod
    async def update_ratings_after_match(
        db: AsyncSession,
        winner_id: Union[UUID4, str],
        loser_id: Union[UUID4, str],
        match: Match,
    ) -> Tuple[int, int]:
        """
        Update ratings after a match using the Elo rating system.
        """
        return await RatingService.update_ratings(
            db=db,
            player1_id=winner_id,
            player2_id=loser_id,
            player1_actual_score=1.0,
            player2_actual_score=0.0,
            log_context="match",
            player1_label="Winner",
            player2_label="Loser",
            match=match,
        )

    @staticmethod
    async def update_ratings_for_draw(
        db: AsyncSession,
        player1_id: Union[UUID4, str],
        player2_id: Union[UUID4, str],
        match: Match,
    ) -> Tuple[int, int]:
        """
        Update ratings after a draw using the Elo rating system.
        """
        return await RatingService.update_ratings(
            db=db,
            player1_id=player1_id,
            player2_id=player2_id,
            player1_actual_score=0.5,
            player2_actual_score=0.5,
            log_context="draw",
            player1_label="Player1",
            player2_label="Player2",
            match=match,
        )

    @staticmethod
    async def fetch_players_and_validate(
        db: AsyncSession, player1_id: UUID4, player2_id: UUID4
    ) -> Tuple[User | None, User | None, str, str]:
        """
        Fetch players from the database and validate their existence.
        """
        from src.storage.repositories.user_repository import get_user_by_id

        player1_id_uuid = (
            uuid.UUID(player1_id) if isinstance(player1_id, str) else player1_id
        )
        player2_id_uuid = (
            uuid.UUID(player2_id) if isinstance(player2_id, str) else player2_id
        )
        player1_id_str = str(player1_id_uuid)
        player2_id_str = str(player2_id_uuid)

        player1 = await get_user_by_id(db, player1_id_uuid)
        player2 = await get_user_by_id(db, player2_id_uuid)

        if not player1 or not player2:
            logger.error(
                f"Failed to update ratings: User not found (player1_id={player1_id}, player2_id={player2_id})"
            )
            return None, None, player1_id_str, player2_id_str

        return player1, player2, player1_id_str, player2_id_str
