from fastapi import (APIRouter, BackgroundTasks, Depends, WebSocket,
                     WebSocketDisconnect)
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.services.auth_dependency import (AccessTokenFromCookie,
                                                   get_current_user, AccessTokenFromWebSocket)
from src.business.services.match import MatchService
from src.config import logger
from src.data.repositories import get_session
from src.data.schemas import (AcceptMatchRequest, CapitulateRequest,
                              FindMatchRequest, UserBaseResponse)
from src.errors import AuthorizationException
from src.presentation.websocket import manager

router = APIRouter(prefix="/match", tags=["match"])
match_logger = logger.getChild("match")


@router.post(
    "/find",
    summary="Find a match",
    description="Adds the user to the matchmaking queue and processes the queue in the background.",
)
async def find_match(
    request_data: FindMatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match find request for user ID: {request_data.user_id}")
    if str(request_data.user_id) != str(current_user.id):
        match_logger.warning(
            f"Unauthorized match request: {request_data.user_id} != {current_user.id}"
        )
        raise AuthorizationException("Can only find matches for yourself")
    return await MatchService.find_match_service(
        request_data.user_id, current_user, db, background_tasks
    )


@router.post(
    "/accept",
    summary="Accept a match",
    description="Accepts a pending match for the authenticated user.",
)
async def accept_match(
    request_data: AcceptMatchRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match accept request for match ID: {request_data.match_id}")
    if str(request_data.user_id) != str(current_user.id):
        match_logger.warning(
            f"Unauthorized accept request: {request_data.user_id} != {current_user.id}"
        )
        raise AuthorizationException("Can only accept matches for yourself")
    return await MatchService.accept_match_service(
        str(request_data.match_id), str(current_user.id), db
    )


@router.post(
    "/decline/{match_id}",
    summary="Decline a match",
    description="Declines a pending match for the authenticated user.",
)
async def decline_match(
    match_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match decline request for match ID: {match_id}")
    return await MatchService.decline_match_service(
        str(match_id), str(current_user.id), db
    )


@router.get(
    "/active",
    summary="Get active match",
    description="Returns the active or pending match for the authenticated user.",
)
async def get_active_match(
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Active match request for user ID: {current_user.id}")
    return await MatchService.get_active_match_service(db)


@router.get(
    "/history",
    summary="Get match history",
    description="Returns the match history for the authenticated user with pagination.",
)
async def get_match_history(
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match history request for user ID: {current_user.id}")
    return await MatchService.get_match_history_service(
        limit, offset, db
    )


@router.get(
    "/details/{match_id}",
    summary="Get match details",
    description="Returns details of a specific match, if the user is a participant.",
)
async def get_match_details(
    match_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match details request for match ID: {match_id}")
    match = await MatchService.get_match_details_service(db)
    if str(current_user.id) not in [str(match.player1_id), str(match.player2_id)]:
        match_logger.warning(
            f"Unauthorized details request: {current_user.id} not in match {match_id}"
        )
        raise AuthorizationException("Not a participant in this match")
    return match


@router.post(
    "/complete/{match_id}",
    summary="Complete a match",
    description="Marks a match as completed with the specified winner, if the user is a participant.",
)
async def complete_match(
    match_id: UUID4,
    winner_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Match complete request for match ID: {match_id}")
    match = await MatchService.get_match_details_service(db)
    if str(current_user.id) not in [str(match.player1_id), str(match.player2_id)]:
        match_logger.warning(
            f"Unauthorized complete request: {current_user.id} not in match {match_id}"
        )
        raise AuthorizationException("Not a participant in this match")
    return await MatchService.complete_match_service(str(winner_id), db)


@router.post(
    "/capitulate",
    summary="Capitulate a match",
    description="Allows a user to surrender a match, declaring the opponent as the winner.",
)
async def capitulate_match(
    request: CapitulateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Capitulate request for match ID: {request.match_id}")
    if str(request.loser_id) != str(current_user.id):
        match_logger.warning(
            f"Unauthorized capitulate request: {request.loser_id} != {current_user.id}"
        )
        raise AuthorizationException("Can only capitulate for yourself")
    await MatchService.capitulate_match_logic(request.match_id, request.loser_id)
    return {"message": "Match capitulated successfully"}


@router.post(
    "/cancel_find",
    summary="Cancel match search",
    description="Removes the authenticated user from the matchmaking queue.",
)
async def cancel_find_match(
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Cancel match find request for user ID: {current_user.id}")
    return await MatchService.cancel_find_match_service(str(current_user.id))


@router.websocket("/ws/{user_id}", name="Match notifications")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: UUID4,
    token_data: dict = Depends(AccessTokenFromWebSocket()),
):
    if str(user_id) != token_data["user"]["id"]:
        match_logger.warning(
            f"Unauthorized WebSocket connection: {user_id} != {token_data['user']['id']}"
        )
        await websocket.close(code=1008, reason="Unauthorized")
        return

    match_logger.info(f"WebSocket connection for user ID: {user_id}")
    await manager.connect(websocket, str(user_id))
    try:
        while True:
            data = await websocket.receive_text()
            match_logger.debug(f"Received message from user {user_id}: {data}")
    except WebSocketDisconnect:
        match_logger.info(f"WebSocket disconnected for user ID: {user_id}")
        manager.disconnect(websocket, str(user_id))
    except Exception as e:
        match_logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        if websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason=f"Internal server error: {str(e)}")