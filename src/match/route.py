import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import (APIRouter, BackgroundTasks, Depends, Request, WebSocket,
                     WebSocketDisconnect)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.model import User
from src.config import logger
from src.db.main import get_session
from src.errors import (AuthorizationException, BadRequestException,
                        DatabaseException, ResourceNotFoundException,
                        ValidationException)

from .models.match import Match, MatchStatus
from .schemas.match import MatchResponse
from .service import add_player_to_queue, process_match_queue
from .websocket import manager

# Create a module-specific logger
match_logger = logger.getChild("match")

router = APIRouter(prefix="/match", tags=["match"])


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
            user = db.query(User).filter(User.id == user_uuid).first()
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
            existing_match = (
                db.query(Match)
                .filter(
                    ((Match.player1_id == user_uuid) | (Match.player2_id == user_uuid))
                    & (
                        (Match.status == MatchStatus.PENDING)
                        | (Match.status == MatchStatus.ACTIVE)
                    )
                )
                .first()
            )
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
            match = (
                db.query(Match)
                .filter(
                    ((Match.player1_id == user_uuid) | (Match.player2_id == user_uuid))
                    & (
                        (Match.status == MatchStatus.PENDING)
                        | (Match.status == MatchStatus.ACTIVE)
                    )
                )
                .first()
            )
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
            matches = (
                db.query(Match)
                .filter(
                    ((Match.player1_id == user_uuid) | (Match.player2_id == user_uuid))
                    & (Match.status == "active")
                )
                .all()
            )
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
            match = db.query(Match).filter(Match.id == match_id).first()
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

        if match.player2_id != user_uuid:
            match_logger.warning(
                f"Match acceptance failed: User not authorized: User ID {user_uuid}, "
                f"Expected Player2 ID {match.player2_id}"
            )
            raise AuthorizationException(detail="Not authorized to accept this match")

        # Check if the match has timed out (15 seconds)
        now = datetime.utcnow()
        timeout_threshold = match.start_time + timedelta(seconds=15)

        if now > timeout_threshold:
            match_logger.warning(
                f"Match acceptance failed: Match timed out: Match ID {match_id}, "
                f"Start time {match.start_time}, Current time {now}"
            )
            try:
                match.status = MatchStatus.DECLINED
                match.end_time = now
                db.flush()  # Flush changes to the database
                db.commit()
                db.refresh(match)
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
            match.status = MatchStatus.ACTIVE
            db.flush()  # Flush changes to the database
            db.commit()
            db.refresh(match)
        except SQLAlchemyError as db_error:
            match_logger.error(
                f"Database error during match status update: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to update match status due to database error"
            )

        match_logger.info(
            f"Match accepted successfully: Match ID {match_id}, User ID {user_uuid}"
        )
        return {"message": "Match accepted"}
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


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: uuid.UUID):
    """
    WebSocket endpoint for real-time match notifications.
    Clients can connect to this endpoint to receive real-time updates about their matches.
    """
    match_logger.info(f"WebSocket connection request from user ID: {user_id}")

    try:
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
