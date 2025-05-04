import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import (APIRouter, BackgroundTasks, Depends, Request, WebSocket,
                     WebSocketDisconnect)
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.model import User
from src.config import logger
from src.db.main import get_session
from src.errors import (AuthorizationException, BadRequestException,
                        DatabaseException, ResourceNotFoundException,
                        ValidationException)

from .models.match import Match, MatchStatus
from .models.problem import Problem
from .schemas.match import MatchResponse
from .schemas.problem import ProblemCreate, ProblemResponse, ProblemUpdate, ProblemSelectionParams
from .service import add_player_to_queue, process_match_queue, select_problem_for_match, send_match_notification
from .websocket import manager
from .rating import update_ratings_after_match

# Create a module-specific logger
match_logger = logger.getChild("match")

router = APIRouter(prefix="/match", tags=["match"])
problem_router = APIRouter(prefix="/problems", tags=["problems"])

# Include the problem router in the main router
router.include_router(problem_router)


@router.post("/find")
async def find_match(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Add a user to the match queue.
    The user will be matched with another user with a similar rating when available.
    Players can only have one active or pending match at a time.
    """
    match_logger.info(f"Match finding request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Match finding failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        try:
            result = await db.execute(select(User).where(User.id == user_uuid))
            user = result.scalars().first()
        except SQLAlchemyError as db_error:
            match_logger.error(f"Database error during user lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to retrieve user due to database error"
            )

        if not user:
            match_logger.warning(
                f"Match finding failed: User not found: ID {user_uuid}"
            )
            raise ResourceNotFoundException(detail="User not found")

        match_logger.debug(
            f"User found: {user.username} (ID: {user_uuid}, Rating: {user.rating})"
        )

        # Check if the user already has an active or pending match
        try:
            # Correct async query
            result = await db.execute(
                select(Match).where(
                    or_(
                        Match.player1_id == user_uuid,
                        Match.player2_id == user_uuid
                    ),
                    or_(
                        Match.status == MatchStatus.PENDING,
                        Match.status == MatchStatus.ACTIVE
                    )
                )
            )
            existing_match = result.scalars().first()
        except SQLAlchemyError as db_error:
            match_logger.error(f"Database error during match lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to check existing matches due to database error"
            )

        if existing_match:
            match_logger.warning(
                f"Match finding failed: User already has an active/pending match: "
                f"User ID {user_uuid}, Match ID {existing_match.id}, Status {existing_match.status}"
            )
            raise BadRequestException(
                detail="You already have an active or pending match"
            )

        # Add the user to the match queue
        try:
            match_logger.info(
                f"Adding user to match queue: ID {user_uuid}, Rating {user.rating}"
            )
            result = await add_player_to_queue(user_uuid, user.rating)
            match_logger.debug(f"Queue result: {result}")
        except Exception as queue_error:
            match_logger.error(f"Error adding user to match queue: {str(queue_error)}")
            raise DatabaseException(detail="Failed to add user to match queue")

        # Start processing the queue in the background
        match_logger.debug("Starting background task to process match queue")
        background_tasks.add_task(process_match_queue, db)

        match_logger.info(f"User added to match queue successfully: ID {user_uuid}")
        return {
            "message": "Added to match queue. You will be matched with a player of similar rating."
        }
    except (
        ResourceNotFoundException,
        ValidationException,
        BadRequestException,
        DatabaseException,
    ):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error during match finding: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while finding a match"
        )


@router.get("/queue/status")
async def get_queue_status(
    user_id: str, db: Session = Depends(get_session), request: Request = None
):
    """
    Check if the user has been matched with another player.
    """
    match_logger.info(f"Queue status check for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Queue status check failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        # Check if the user is in a pending or active match
        try:
            result = await db.execute(
                select(Match).where(
                    or_(
                        Match.player1_id == user_uuid,
                        Match.player2_id == user_uuid
                    ),
                    or_(
                        Match.status == MatchStatus.PENDING,
                        Match.status == MatchStatus.ACTIVE
                    )
                )
            )
            match = result.scalars().first()
        except SQLAlchemyError as db_error:
            match_logger.error(f"Database error during match lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to check match status due to database error"
            )

        if match:
            opponent_id = (
                match.player2_id if match.player1_id == user_uuid else match.player1_id
            )
            match_logger.info(
                f"Match found for user ID {user_uuid}: Match ID {match.id}, "
                f"Status {match.status}, Opponent ID {opponent_id}"
            )
            return {
                "in_match": True,
                "match_id": match.id,
                "status": match.status,
                "opponent_id": str(opponent_id),
            }

        match_logger.info(f"No active match found for user ID: {user_uuid}")
        return {"in_match": False, "message": "Still in queue or not in queue"}
    except (ResourceNotFoundException, DatabaseException):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error during queue status check: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while checking queue status"
        )


@router.get("/active", response_model=List[MatchResponse])
async def get_active_matches(
    user_id: str, db: Session = Depends(get_session), request: Request = None
):
    match_logger.info(f"Active matches request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Active matches request failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        try:
            # Async query
            result = await db.execute(
                select(Match).where(
                    or_(
                        Match.player1_id == user_uuid,
                        Match.player2_id == user_uuid
                    ),
                    Match.status == MatchStatus.ACTIVE
                )
            )
            matches = result.scalars().all()
        except SQLAlchemyError as db_error:
            match_logger.error(
                f"Database error during active matches lookup: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to retrieve active matches due to database error"
            )

        match_count = len(matches)
        match_logger.info(
            f"Found {match_count} active matches for user ID: {user_uuid}"
        )

        if match_count > 0:
            match_ids = [match.id for match in matches]
            match_logger.debug(f"Active match IDs for user {user_uuid}: {match_ids}")

        return matches
    except (ResourceNotFoundException, DatabaseException):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error retrieving active matches: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while retrieving active matches"
        )


@router.post("/accept/{match_id}")
async def accept_match(
    match_id: int,
    user_id: str,
    db: Session = Depends(get_session),
    request: Request = None,
):
    match_logger.info(
        f"Match acceptance request: Match ID {match_id}, User ID {user_id}"
    )

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Match acceptance failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        try:
            result = await db.execute(select(Match).where(Match.id == match_id))
            match = result.scalars().first()
        except SQLAlchemyError as db_error:
            match_logger.error(f"Database error during match lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to retrieve match due to database error"
            )

        if not match:
            match_logger.warning(
                f"Match acceptance failed: Match not found: ID {match_id}"
            )
            raise ResourceNotFoundException(detail="Match not found")

        match_logger.debug(
            f"Match found: ID {match_id}, Player1 {match.player1_id}, Player2 {match.player2_id}, Status {match.status}"
        )

        # Check if the user is either player1 or player2
        if match.player1_id != user_uuid and match.player2_id != user_uuid:
            match_logger.warning(
                f"Match acceptance failed: User not authorized: User ID {user_uuid}, "
                f"Expected Player1 ID {match.player1_id} or Player2 ID {match.player2_id}"
            )
            raise AuthorizationException(detail="Not authorized to accept this match")

        # Check if the match has timed out (15 seconds)
        now = datetime.utcnow()
        timeout_threshold = match.start_time + timedelta(seconds=60)

        if now > timeout_threshold:
            match_logger.warning(
                f"Match acceptance failed: Match timed out: Match ID {match_id}, "
                f"Start time {match.start_time}, Current time {now}"
            )
            try:
                match.status = MatchStatus.DECLINED
                match.end_time = now
                await db.flush()
                await db.commit()
                await db.refresh(match)
                match_logger.info(
                    f"Match automatically declined due to timeout: Match ID {match_id}"
                )
            except SQLAlchemyError as db_error:
                match_logger.error(
                    f"Database error during match status update: {str(db_error)}"
                )
                raise DatabaseException(
                    detail="Failed to update match status due to database error"
                )

            raise BadRequestException(
                detail="Match has timed out and was automatically declined"
            )

        try:
            # Update the acceptance status for the current player
            if match.player1_id == user_uuid:
                match.player1_accepted = True
                match_logger.info(f"Player 1 (ID: {user_uuid}) accepted match {match_id}")
            else:  # player2_id == user_uuid
                match.player2_accepted = True
                match_logger.info(f"Player 2 (ID: {user_uuid}) accepted match {match_id}")

            # If both players have accepted, set the match to ACTIVE
            if match.player1_accepted and match.player2_accepted:
                match.status = MatchStatus.ACTIVE
                match_logger.info(f"Both players accepted match {match_id}, setting status to ACTIVE")

            await db.flush()  # Flush changes to the database
            await db.commit()
            await db.refresh(match)

            # Notify the other player about the acceptance
            other_player_id = match.player2_id if match.player1_id == user_uuid else match.player1_id
            await send_match_notification(other_player_id, match.id, user_uuid, match.status)
        except SQLAlchemyError as db_error:
            match_logger.error(
                f"Database error during match status update: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to update match status due to database error"
            )

        match_logger.info(
            f"Match acceptance processed: Match ID {match_id}, User ID {user_uuid}, Status {match.status}"
        )

        # Return appropriate message based on match status
        if match.status == MatchStatus.ACTIVE:
            return {"message": "Match accepted by both players and is now active"}
        else:
            # Calculate which player still needs to accept
            waiting_for = "player1" if not match.player1_accepted else "player2"
            return {
                "message": "Match acceptance recorded, waiting for other player to accept",
                "status": match.status,
                "player1_accepted": match.player1_accepted,
                "player2_accepted": match.player2_accepted,
                "waiting_for": waiting_for
            }
    except (
        ResourceNotFoundException,
        AuthorizationException,
        ValidationException,
        BadRequestException,
        DatabaseException,
    ):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error during match acceptance: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while accepting the match"
        )


@router.post("/complete/{match_id}")
async def complete_match(
    match_id: int,
    user_id: str,
    winner_id: str,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Complete a match and update player ratings.
    Only the match creator (player1) can complete a match.
    The winner_id must be either player1_id or player2_id.
    """
    match_logger.info(
        f"Match completion request: Match ID {match_id}, User ID {user_id}, Winner ID {winner_id}"
    )

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
            winner_uuid = uuid.UUID(winner_id)
        except ValueError:
            match_logger.warning(
                f"Match completion failed: Invalid ID format: User ID {user_id}, Winner ID {winner_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        try:
            result = await db.execute(select(Match).where(Match.id == match_id))
            match = result.scalars().first()
        except SQLAlchemyError as db_error:
            match_logger.error(f"Database error during match lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to retrieve match due to database error"
            )

        if not match:
            match_logger.warning(
                f"Match completion failed: Match not found: ID {match_id}"
            )
            raise ResourceNotFoundException(detail="Match not found")

        match_logger.debug(
            f"Match found: ID {match_id}, Player1 {match.player1_id}, Player2 {match.player2_id}, Status {match.status}"
        )

        # Only player1 (match creator) can complete the match
        if match.player1_id != user_uuid:
            match_logger.warning(
                f"Match completion failed: User not authorized: User ID {user_uuid}, "
                f"Expected Player1 ID {match.player1_id}"
            )
            raise AuthorizationException(detail="Not authorized to complete this match")

        # Winner must be either player1 or player2
        if winner_uuid != match.player1_id and winner_uuid != match.player2_id:
            match_logger.warning(
                f"Match completion failed: Invalid winner: Winner ID {winner_uuid}, "
                f"Expected either {match.player1_id} or {match.player2_id}"
            )
            raise BadRequestException(detail="Winner must be one of the match participants")

        # Match must be in ACTIVE status
        if match.status != MatchStatus.ACTIVE:
            match_logger.warning(
                f"Match completion failed: Invalid match status: {match.status}, "
                f"Expected {MatchStatus.ACTIVE}"
            )
            raise BadRequestException(detail=f"Match must be in {MatchStatus.ACTIVE} status to complete")

        try:
            # Update match status and set winner
            match.status = MatchStatus.COMPLETED
            match.winner_id = winner_uuid
            match.end_time = datetime.utcnow()

            # Update player ratings using Elo system
            loser_id = match.player2_id if winner_uuid == match.player1_id else match.player1_id
            new_ratings = await update_ratings_after_match(db, winner_uuid, loser_id)

            await db.commit()
            await db.refresh(match)

            match_logger.info(
                f"Match completed successfully: Match ID {match_id}, "
                f"Winner ID {winner_uuid}, New ratings: {new_ratings}"
            )

            return {
                "message": "Match completed successfully",
                "match_id": match.id,
                "winner_id": str(match.winner_id),
                "new_ratings": new_ratings
            }
        except SQLAlchemyError as db_error:
            match_logger.error(
                f"Database error during match completion: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to complete match due to database error"
            )
    except (
        ResourceNotFoundException,
        AuthorizationException,
        ValidationException,
        BadRequestException,
        DatabaseException,
    ):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error during match completion: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while completing the match"
        )


# Problem management endpoints

@problem_router.post("/", response_model=ProblemResponse)
async def create_problem(
    problem: ProblemCreate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Create a new problem.
    """
    match_logger.info(f"Creating new problem: {problem.title}")

    try:
        new_problem = Problem(
            rating=problem.rating,
            topics=problem.topics,
            title=problem.title,
            description=problem.description,
            difficulty=problem.difficulty,
            bucket_path=problem.bucket_path,
        )

        db.add(new_problem)
        await db.commit()
        await db.refresh(new_problem)

        match_logger.info(f"Problem created successfully: ID {new_problem.id}")
        return new_problem
    except SQLAlchemyError as db_error:
        match_logger.error(f"Database error creating problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to create problem due to database error")
    except Exception as e:
        match_logger.error(f"Unexpected error creating problem: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred while creating the problem")


@problem_router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: int,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Get a problem by ID.
    """
    match_logger.info(f"Getting problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            match_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        match_logger.info(f"Problem retrieved successfully: ID {problem_id}")
        return problem
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        match_logger.error(f"Database error retrieving problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to retrieve problem due to database error")
    except Exception as e:
        match_logger.error(f"Unexpected error retrieving problem: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred while retrieving the problem")


@problem_router.put("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: int,
    problem_update: ProblemUpdate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Update a problem.
    """
    match_logger.info(f"Updating problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            match_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        # Update fields if provided
        update_data = problem_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(problem, key, value)

        problem.updated_at = datetime.now()

        await db.commit()
        await db.refresh(problem)

        match_logger.info(f"Problem updated successfully: ID {problem_id}")
        return problem
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        match_logger.error(f"Database error updating problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to update problem due to database error")
    except Exception as e:
        match_logger.error(f"Unexpected error updating problem: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred while updating the problem")


@problem_router.delete("/{problem_id}")
async def delete_problem(
    problem_id: int,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Delete a problem.
    """
    match_logger.info(f"Deleting problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            match_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        await db.delete(problem)
        await db.commit()

        match_logger.info(f"Problem deleted successfully: ID {problem_id}")
        return {"message": f"Problem {problem_id} deleted successfully"}
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        match_logger.error(f"Database error deleting problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to delete problem due to database error")
    except Exception as e:
        match_logger.error(f"Unexpected error deleting problem: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred while deleting the problem")


@problem_router.get("/", response_model=List[ProblemResponse])
async def list_problems(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    List all problems with pagination.
    """
    match_logger.info(f"Listing problems: skip={skip}, limit={limit}")

    try:
        result = await db.execute(select(Problem).offset(skip).limit(limit))
        problems = result.scalars().all()

        match_logger.info(f"Retrieved {len(problems)} problems")
        return problems
    except SQLAlchemyError as db_error:
        match_logger.error(f"Database error listing problems: {str(db_error)}")
        raise DatabaseException(detail="Failed to list problems due to database error")
    except Exception as e:
        match_logger.error(f"Unexpected error listing problems: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred while listing problems")


@router.post("/submit-solution/{match_id}")
async def submit_solution(
    match_id: int,
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
    match_logger.info(
        f"Solution submission: Match ID {match_id}, User ID {user_id}, Correct: {is_correct}"
    )

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Solution submission failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        # Get the match
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalars().first()

        if not match:
            match_logger.warning(
                f"Solution submission failed: Match not found: ID {match_id}"
            )
            raise ResourceNotFoundException(detail="Match not found")

        # Check if user is part of the match
        if match.player1_id != user_uuid and match.player2_id != user_uuid:
            match_logger.warning(
                f"Solution submission failed: User not in match: User ID {user_uuid}, "
                f"Match ID {match_id}"
            )
            raise AuthorizationException(detail="Not authorized to submit solution for this match")

        # Check if match is active
        if match.status != MatchStatus.ACTIVE:
            match_logger.warning(
                f"Solution submission failed: Invalid match status: {match.status}, "
                f"Expected {MatchStatus.ACTIVE}"
            )
            raise BadRequestException(detail=f"Match must be in {MatchStatus.ACTIVE} status to submit solution")

        # If solution is correct, end the match and update ratings
        if is_correct:
            match_logger.info(
                f"Correct solution submitted: Match ID {match_id}, User ID {user_uuid}"
            )

            # Update match status and set winner
            match.status = MatchStatus.COMPLETED
            match.winner_id = user_uuid
            match.end_time = datetime.utcnow()

            # Update player ratings
            loser_id = match.player2_id if user_uuid == match.player1_id else match.player1_id
            new_ratings = await update_ratings_after_match(db, user_uuid, loser_id)

            await db.commit()
            await db.refresh(match)

            # Notify both players about match completion
            winner_msg = {
                "event": "match_completed",
                "match_id": match.id,
                "winner_id": str(user_uuid),
                "new_rating": new_ratings[0] if new_ratings else None
            }

            loser_msg = {
                "event": "match_completed",
                "match_id": match.id,
                "winner_id": str(user_uuid),
                "new_rating": new_ratings[1] if new_ratings else None
            }

            await manager.send_match_notification(str(user_uuid), winner_msg)
            await manager.send_match_notification(str(loser_id), loser_msg)

            match_logger.info(
                f"Match completed successfully: Match ID {match_id}, "
                f"Winner ID {user_uuid}, New ratings: {new_ratings}"
            )

            return {
                "message": "Correct solution submitted. Match completed.",
                "match_id": match.id,
                "winner_id": str(match.winner_id),
                "new_ratings": new_ratings
            }
        else:
            # If solution is incorrect, just return a message
            match_logger.info(
                f"Incorrect solution submitted: Match ID {match_id}, User ID {user_uuid}"
            )

            return {
                "message": "Incorrect solution submitted. Match continues."
            }
    except (
        ResourceNotFoundException,
        AuthorizationException,
        BadRequestException,
        DatabaseException,
    ):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        match_logger.error(f"Unexpected error during solution submission: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while submitting the solution"
        )


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time match notifications.
    Clients can connect to this endpoint to receive real-time updates about their matches.
    """
    match_logger.info(f"WebSocket connection request from user ID: {user_id}")

    try:
        # user_id is already a string from the path parameter
        await manager.connect(websocket, user_id)
        match_logger.info(f"WebSocket connection established for user ID: {user_id}")

        try:
            while True:
                # Wait for messages from the client (can be used for ping/pong)
                data = await websocket.receive_text()
                match_logger.debug(
                    f"WebSocket message received from user ID {user_id}: {data}"
                )
        except WebSocketDisconnect:
            match_logger.info(f"WebSocket disconnected for user ID: {user_id}")
            manager.disconnect(websocket, user_id)
        except Exception as e:
            match_logger.error(f"WebSocket error for user ID {user_id}: {str(e)}")
            manager.disconnect(websocket, user_id)
            raise
    except Exception as e:
        match_logger.error(
            f"Failed to establish WebSocket connection for user ID {user_id}: {str(e)}"
        )
        raise
