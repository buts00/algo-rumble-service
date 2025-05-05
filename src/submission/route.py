import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.model import User
from src.config import logger
from src.db.main import get_session
from src.errors import (AuthorizationException, BadRequestException,
                        DatabaseException, ResourceNotFoundException)
from src.match.models.match import Match, MatchStatus
from src.match.rating import update_ratings_after_match
from src.match.service import send_match_notification

# Create a module-specific logger
submission_logger = logger.getChild("submission")

submission_router = APIRouter(prefix="/submissions", tags=["submissions"])


@submission_router.post("/match/{match_id}")
async def submit_solution(
    match_id: uuid.UUID,
    user_id: str,
    is_correct: bool,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Submit a solution for a match.
    If the solution is correct, the match ends instantly and the player who submitted the solution wins.
    Player ratings are updated accordingly.
    """
    submission_logger.info(
        f"Solution submission: Match ID {match_id}, User ID {user_id}, Correct: {is_correct}"
    )

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            submission_logger.warning(
                f"Solution submission failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        # Get the match
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalars().first()

        if not match:
            submission_logger.warning(
                f"Solution submission failed: Match not found: ID {match_id}"
            )
            raise ResourceNotFoundException(detail="Match not found")

        # Check if user is part of the match
        if match.player1_id != user_uuid and match.player2_id != user_uuid:
            submission_logger.warning(
                f"Solution submission failed: User not in match: User ID {user_uuid}, "
                f"Match ID {match_id}"
            )
            raise AuthorizationException(
                detail="Not authorized to submit solution for this match"
            )

        # Check if match is active
        if match.status != MatchStatus.ACTIVE:
            submission_logger.warning(
                f"Solution submission failed: Match not active: ID {match_id}, "
                f"Status {match.status}"
            )
            raise BadRequestException(detail="Match is not active")

        # If solution is correct, end the match and update ratings
        if is_correct:
            match.status = MatchStatus.COMPLETED
            match.winner_id = user_uuid
            match.end_time = datetime.now()

            # Get both players
            player1_result = await db.execute(
                select(User).where(User.id == match.player1_id)
            )
            player1 = player1_result.scalars().first()

            player2_result = await db.execute(
                select(User).where(User.id == match.player2_id)
            )
            player2 = player2_result.scalars().first()

            # Update ratings
            if player1 and player2:
                winner = player1 if match.winner_id == player1.id else player2
                loser = player2 if match.winner_id == player1.id else player1

                update_ratings_after_match(winner, loser)
                await db.commit()

                submission_logger.info(
                    f"Ratings updated: Winner {winner.username} ({winner.rating}), "
                    f"Loser {loser.username} ({loser.rating})"
                )

                # Send match completion notification to both players
                winner_notification = {
                    "type": "match_completed",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "win",
                    "new_rating": winner.rating,
                }
                await send_match_notification(str(winner.id), winner_notification)

                loser_notification = {
                    "type": "match_completed",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "loss",
                    "new_rating": loser.rating,
                }
                await send_match_notification(str(loser.id), loser_notification)

            submission_logger.info(
                f"Match completed: ID {match_id}, Winner: {user_uuid}"
            )
            return {"message": "Solution correct, match completed"}
        else:
            submission_logger.info(
                f"Incorrect solution submitted: Match ID {match_id}, User ID {user_uuid}"
            )
            return {"message": "Solution incorrect, match continues"}

    except (ResourceNotFoundException, AuthorizationException, BadRequestException):
        raise
    except SQLAlchemyError as db_error:
        submission_logger.error(f"Database error during submission: {str(db_error)}")
        raise DatabaseException(
            detail="Failed to process submission due to database error"
        )
    except Exception as e:
        submission_logger.error(f"Unexpected error during submission: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while processing the submission"
        )
