import asyncio
import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas import User, UserBaseResponse
from src.config import logger, Config
from src.data.repositories import get_session
from src.data.schemas.match import CapitulateRequest
from src.errors import (
    AuthorizationException,
    BadRequestException,
    DatabaseException,
    ResourceNotFoundException,
    ValidationException,
)

from src.data.schemas import AcceptMatchRequest, FindMatchRequest, Match, MatchStatus
from src.business.services.match import (
    add_player_to_queue,
    process_match_queue,
    send_match_notification,
    capitulate_match_logic,
    remove_player_from_queue,
    accept_match_service,
)
from src.business.services.auth_dependency import get_current_user
from src.presentation.websocket import manager

# Create a module-specific logger
match_logger = logger.getChild("match")

router = APIRouter(prefix="/match", tags=["match"])


async def match_acceptance_timeout(match_id: str, db: AsyncSession):
    await asyncio.sleep(Config.MATCH_ACCEPT_TIMEOUT_SECONDS)
    result = await db.execute(select(Match).where(Match.id == uuid.UUID(match_id)))
    match = result.scalars().first()
    if match and match.status == MatchStatus.PENDING:
        # Determine who did not accept
        not_accepted = []
        if not match.player1_accepted:
            not_accepted.append(str(match.player1_id))
        if not match.player2_accepted:
            not_accepted.append(str(match.player2_id))
        match.status = MatchStatus.CANCELLED
        match.end_time = datetime.utcnow()
        db.add(match)
        await db.commit()
        # Get usernames
        result1 = await db.execute(select(User).where(User.id == match.player1_id))
        player1 = result1.scalar_one_or_none()
        result2 = await db.execute(select(User).where(User.id == match.player2_id))
        player2 = result2.scalar_one_or_none()
        for user, other in [(player1, player2), (player2, player1)]:
            if user:
                await send_match_notification(
                    str(user.id),
                    {
                        "status": "match_cancelled",
                        "match_id": str(match.id),
                        "reason": (
                            f"User '{other.username}' did not accept in time"
                            if other
                            and not (
                                match.player1_accepted
                                if user == player1
                                else match.player2_accepted
                            )
                            else "You did not accept in time"
                        ),
                    },
                )


async def match_draw_timeout(match_id: str, db: AsyncSession):
    await asyncio.sleep(Config.MATCH_DURATION_SECONDS)
    result = await db.execute(select(Match).where(Match.id == uuid.UUID(match_id)))
    match = result.scalars().first()
    if match and match.status == MatchStatus.ACTIVE:
        match.status = MatchStatus.COMPLETED
        match.end_time = datetime.utcnow()
        db.add(match)
        await db.commit()
        # Get usernames
        result1 = await db.execute(select(User).where(User.id == match.player1_id))
        player1 = result1.scalar_one_or_none()
        result2 = await db.execute(select(User).where(User.id == match.player2_id))
        player2 = result2.scalar_one_or_none()
        for user in [player1, player2]:
            if user:
                await send_match_notification(
                    str(user.id),
                    {
                        "status": "match_draw",
                        "match_id": str(match.id),
                        "message": "Match ended in a draw. No one submitted a correct solution in 45 minutes.",
                    },
                )


@router.post("/find")
async def find_match(
    request_data: FindMatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
    request: Request = None,
):
    """
    Add a user to the match queue.
    The user will be matched with another user with a similar rating when available.
    Players can only have one active or pending match at a time.
    """
    user_id = request_data.user_id
    match_logger.info(f"Match finding request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Match finding failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Check if user exists
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if not user:
            match_logger.warning(f"Match finding failed: User not found: {user_id}")
            raise ResourceNotFoundException(detail="User not found")

        # Check if user already has an active or pending match
        result = await db.execute(
            select(Match).where(
                or_(
                    Match.player1_id == user_uuid,
                    Match.player2_id == user_uuid,
                ),
                or_(
                    Match.status == MatchStatus.ACTIVE,
                    Match.status == MatchStatus.PENDING,
                    Match.status == MatchStatus.CREATED,
                ),
            )
        )
        active_match = result.scalars().first()

        if active_match:
            match_logger.warning(
                f"Match finding failed: User already has an active match: {user_id}"
            )
            raise ValidationException(
                detail="You already have an active or pending match"
            )

        # Add player to queue (returns True if added, False if already in queue)
        added = await add_player_to_queue(user_uuid, user.rating)
        if not added:
            match_logger.info(f"User {user_id} is already searching for a match.")
            return {
                "status": "already_searching",
                "message": "You are already searching for a match",
            }
        match_logger.info(f"User added to match queue: {user_id}")

        # Process match queue in background, pass the timeout callback
        background_tasks.add_task(
            process_match_queue, db, match_acceptance_timeout, match_draw_timeout
        )

        return {"status": "queued", "message": "You have been added to the match queue"}
    except (
        BadRequestException,
        ResourceNotFoundException,
        ValidationException,
        DatabaseException,
    ) as e:
        raise e
    except Exception as e:
        match_logger.error(f"Unexpected error during match finding: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")


@router.post("/accept")
async def accept_match(
    request_data: AcceptMatchRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
    request: Request = None,
):
    """
    Accept a match invitation.
    Both players must accept for the match to start.
    """
    user_id = str(current_user.id)  # Використовуємо ID автентифікованого користувача
    match_id = request_data.match_id
    match_logger.info(
        f"Match acceptance request for user ID: {user_id}, match ID: {match_id}"
    )

    try:
        # Викликаємо шар бізнес-логіки для обробки прийняття матчу
        result = await accept_match_service(db, match_id, user_id)
        match_logger.info(
            f"Match acceptance processed successfully: user={user_id}, match={match_id}"
        )
        return result
    except (
        BadRequestException,
        ResourceNotFoundException,
        ValidationException,
        AuthorizationException,
        DatabaseException,
    ) as e:
        raise e
    except SQLAlchemyError as e:
        match_logger.error(f"Database error during match acceptance: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="Database error occurred")
    except Exception as e:
        match_logger.error(f"Unexpected error during match acceptance: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="An unexpected error occurred")


@router.post("/decline/{match_id}")
async def decline_match(
    match_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
    request: Request = None,
):
    """
    Decline a match invitation.
    If either player declines, the match is cancelled.
    """
    match_logger.info(
        f"Match decline request for user ID: {user_id}, match ID: {match_id}"
    )

    try:
        # Convert IDs to UUID
        try:
            user_uuid = uuid.UUID(user_id)
            match_uuid = uuid.UUID(match_id)
        except ValueError:
            match_logger.warning(
                f"Match decline failed: Invalid ID format: user={user_id}, match={match_id}"
            )
            raise BadRequestException(detail="Invalid ID format")

        # Check if user exists
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if not user:
            match_logger.warning(f"Match decline failed: User not found: {user_id}")
            raise ResourceNotFoundException(detail="User not found")

        # Check if match exists
        result = await db.execute(select(Match).where(Match.id == match_uuid))
        match = result.scalars().first()
        if not match:
            match_logger.warning(f"Match decline failed: Match not found: {match_id}")
            raise ResourceNotFoundException(detail="Match not found")

        # Check if user is part of the match
        if match.player1_id != user_uuid and match.player2_id != user_uuid:
            match_logger.warning(
                f"Match decline failed: User not part of match: user={user_id}, match={match_id}"
            )
            raise AuthorizationException(detail="You are not part of this match")

        # Check if match is in the correct state
        if match.status != MatchStatus.PENDING:
            match_logger.warning(
                f"Match decline failed: Match not in PENDING state: {match_id}, current state: {match.status}"
            )
            raise ValidationException(detail="Match is not in a pending state")

        # Update match status
        match.status = MatchStatus.DECLINED
        match.end_time = datetime.utcnow()
        match_logger.info(f"Match declined: {match_id} by user {user_id}")

        # Notify the other player
        other_player_id = (
            str(match.player2_id)
            if match.player1_id == user_uuid
            else str(match.player1_id)
        )
        await send_match_notification(
            other_player_id,
            {
                "status": "match_declined",
                "match_id": str(match.id),
                "declined_by": str(user_uuid),
            },
        )

        # Commit changes
        db.add(match)
        await db.commit()
        match_logger.info(
            f"Match decline processed successfully: user={user_id}, match={match_id}"
        )

        return {
            "status": "declined",
            "match_id": str(match.id),
            "match_status": match.status,
        }
    except (
        BadRequestException,
        ResourceNotFoundException,
        ValidationException,
        AuthorizationException,
        DatabaseException,
    ) as e:
        raise e
    except SQLAlchemyError as e:
        match_logger.error(f"Database error during match decline: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="Database error occurred")
    except Exception as e:
        match_logger.error(f"Unexpected error during match decline: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="An unexpected error occurred")


@router.get("/active/{user_id}")
async def get_active_match(
    user_id: str, db: AsyncSession = Depends(get_session), request: Request = None
):
    """
    Get the active match for a user.
    """
    match_logger.info(f"Active match request for user ID: {user_id}")

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            match_logger.warning(
                f"Active match request failed: Invalid user ID format: {user_id}"
            )
            raise BadRequestException(detail="Invalid user ID format")

        # Check if user exists
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if not user:
            match_logger.warning(
                f"Active match request failed: User not found: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        # Find active match
        result = await db.execute(
            select(Match).where(
                or_(
                    Match.player1_id == user_uuid,
                    Match.player2_id == user_uuid,
                ),
                or_(
                    Match.status == MatchStatus.ACTIVE,
                    Match.status == MatchStatus.PENDING,
                    Match.status == MatchStatus.CREATED,
                ),
            )
        )
        active_match = result.scalars().first()

        if not active_match:
            match_logger.info(f"No active match found for user: {user_id}")
            return {"has_active_match": False}

        # Get opponent details
        opponent_id = (
            active_match.player2_id
            if active_match.player1_id == user_uuid
            else active_match.player1_id
        )
        result = await db.execute(select(User).where(User.id == opponent_id))
        opponent = result.scalar_one_or_none()

        match_logger.info(f"Active match found for user: {user_id}")
        return {
            "has_active_match": True,
            "match_id": str(active_match.id),
            "status": active_match.status,
            "opponent": {
                "id": str(opponent.id) if opponent else "",
                "username": opponent.username if opponent else "",
                "rating": opponent.rating if opponent else 0,
            },
            "problem_id": (
                str(active_match.problem_id) if active_match.problem_id else None
            ),
            "start_time": active_match.start_time,
            "player_accepted": (
                active_match.player1_accepted
                if active_match.player1_id == user_uuid
                else active_match.player2_accepted
            ),
        }
    except (BadRequestException, ResourceNotFoundException, DatabaseException) as e:
        raise e
    except Exception as e:
        match_logger.error(f"Unexpected error during active match request: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred")


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time match notifications.
    """
    match_logger.info(f"WebSocket connection request for user ID: {user_id}")

    try:
        await manager.connect(websocket, user_id)
        match_logger.info(f"WebSocket connection established for user ID: {user_id}")

        try:
            while True:
                # Wait for messages from the client
                # This keeps the connection open
                data = await websocket.receive_text()
                match_logger.debug(f"Received message from user {user_id}: {data}")
        except WebSocketDisconnect:
            match_logger.info(f"WebSocket disconnected for user ID: {user_id}")
            manager.disconnect(websocket, user_id)
    except Exception as e:
        match_logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        if websocket.client_state == websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason=f"Internal server error: {str(e)}")


async def notify_match_found(match, user_id, opponent_id, db: AsyncSession):
    # Only send if match.id and match.problem_id are valid
    if match.id and match.problem_id:
        # Get opponent username
        result = await db.execute(select(User).where(User.id == opponent_id))
        opponent = result.scalar_one_or_none()
        await send_match_notification(
            user_id,
            {
                "status": "match_found",
                "match_id": str(match.id),
                "opponent_username": opponent.username if opponent else "",
                "problem_id": str(match.problem_id),
            },
        )
    else:
        match_logger.warning(
            f"Not sending match_found notification due to missing match_id/problem_id: "
            f"match_id={match.id}, problem_id={match.problem_id}, user_id={user_id}, opponent_id={opponent_id}"
        )


@router.post("/capitulate")
async def capitulate_match(
    request: CapitulateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    try:
        await capitulate_match_logic(db, request.match_id, request.loser_id)
        return {"message": "Match capitulated successfully."}
    except Exception as e:
        match_logger.error(f"Failed to capitulate match: {e}")
        raise BadRequestException("Could not capitulate match.")


@router.post("/cancel_find")
async def cancel_find_match(
    request_data: FindMatchRequest,
    current_user: UserBaseResponse = Depends(get_current_user),
):
    """
    Cancel matchmaking search for a user (remove from queue).
    """
    user_id = request_data.user_id
    match_logger.info(f"Cancel find request for user ID: {user_id}")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        match_logger.warning(f"Cancel find failed: Invalid user ID format: {user_id}")
        raise BadRequestException(detail="Invalid user ID format")

    removed = await remove_player_from_queue(user_uuid)
    if removed:
        return {
            "status": "cancelled",
            "message": "You have been removed from the match queue",
        }
    else:
        return {"status": "not_found", "message": "You were not in the match queue"}
