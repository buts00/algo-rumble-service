import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.business.services.match_rating import RatingService
from src.config import logger
from src.data.repositories.submission import (check_solution, fetch_test_cases,
                                              get_match_by_id,
                                              get_problem_by_id,
                                              get_users_by_ids)
from src.data.schemas.match import MatchStatus
from src.errors import (AuthorizationException, BadRequestException,
                        ResourceNotFoundException)
from src.presentation.websocket import manager

# Create a module-specific logger
submission_logger = logger.getChild("submission")


class SubmissionService:
    @staticmethod
    async def process_submission(
        user_id: str,
        match_id: str,
        code: str,
        language: str,
        db: AsyncSession,
    ) -> dict:
        """
        Process a solution submission for a match.

        Args:
            user_id: The ID of the user submitting the solution
            match_id: The ID of the match
            code: The solution code
            language: The programming language
            db: Database session

        Returns:
            A dictionary with the result of the submission
        """
        submission_logger.info(
            f"Solution submission: Match ID {match_id}, User ID {user_id}, Language: {language}"
        )

        try:
            # Convert user_id and match_id to UUID
            try:
                user_uuid = uuid.UUID(user_id)
                match_uuid = uuid.UUID(match_id)
            except ValueError:
                submission_logger.warning(
                    f"Solution submission failed: Invalid user ID format: {user_id}"
                )
                raise ResourceNotFoundException(detail="User not found")

            # Get the match
            match = await get_match_by_id(db, match_uuid)

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

            # Get the problem associated with the match
            if not match.problem_id:
                submission_logger.warning(
                    f"Solution submission failed: No problem associated with match: ID {match_id}"
                )
                raise BadRequestException(
                    detail="No problem associated with this match"
                )

            problem = await get_problem_by_id(db, match.problem_id)

            # Fetch test cases from Digital Ocean
            test_cases = fetch_test_cases(str(problem.id))
            if not test_cases:
                submission_logger.warning(
                    f"Solution submission failed: No test cases found for problem: ID {match.problem_id}"
                )
                raise BadRequestException(detail="No test cases found for this problem")

            # Run the solution against test cases
            is_correct = await check_solution(code, language, test_cases)

            # If solution is correct, end the match and update ratings
            if is_correct:
                match.status = MatchStatus.COMPLETED
                match.winner_id = user_uuid
                match.end_time = datetime.now()

                # Get both players
                users = await get_users_by_ids(
                    db, [str(match.player1_id), str(match.player2_id)]
                )
                user_map = {u.id: u for u in users}
                winner = user_map.get(user_uuid)
                loser = user_map.get(
                    match.player2_id
                    if match.player1_id == user_uuid
                    else match.player1_id
                )

                if not winner or not loser:
                    submission_logger.error("Could not load player data")
                    raise ResourceNotFoundException(detail="Could not load player data")

                old_winner_rating = winner.rating
                old_loser_rating = loser.rating

                await RatingService.update_ratings_after_match(db, winner.id, loser.id)
                await db.commit()

                submission_logger.info(
                    f"Ratings updated: Winner {winner.username} ({winner.rating}), "
                    f"Loser {loser.username} ({loser.rating})"
                )

                # Send match completion notification to both players
                winner_notification = {
                    "status": "match_completed",
                    "message": "Congratulations! You solved the problem correctly and won the match.",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "win",
                    "new_rating": winner.rating,
                    "old_rating": old_winner_rating,
                }
                await manager.send_match_notification(
                    str(winner.id), winner_notification
                )

                loser_notification = {
                    "status": "match_completed",
                    "message": f"Your opponent '{winner.username}' solved the problem and won the match.",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "loss",
                    "new_rating": loser.rating,
                    "old_rating": old_loser_rating,
                }
                await manager.send_match_notification(str(loser.id), loser_notification)

                submission_logger.info(
                    f"Match completed: ID {match_id}, Winner: {user_uuid}"
                )
                return {
                    "is_correct": True,
                    "message": "Solution correct, match completed",
                }
            else:
                # Notify user about incorrect solution
                await manager.send_match_notification(
                    user_id,
                    {
                        "status": "submission_result",
                        "is_correct": False,
                        "message": "Incorrect solution. Try again!",
                        "match_id": match_id,
                        "problem_id": str(match.problem_id),
                    },
                )
                submission_logger.info(
                    f"Incorrect solution submitted: Match ID {match_id}, User ID {user_uuid}"
                )
                return {
                    "is_correct": False,
                    "message": "Solution incorrect, match continues",
                }

        except (ResourceNotFoundException, AuthorizationException, BadRequestException):
            raise
        except Exception as e:
            submission_logger.error(f"Unexpected error during submission: {str(e)}")
            raise
