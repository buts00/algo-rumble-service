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
    summary="Знайти матч",
    description="Додає користувача до черги підбору матчів і обробляє чергу у фоновому режимі.",
)
async def find_match(
    request_data: FindMatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на пошук матчу для користувача ID: {request_data.user_id}")
    if str(request_data.user_id) != str(current_user.id):
        match_logger.warning(
            f"Несанкціонований запит на матч: {request_data.user_id} != {current_user.id}"
        )
        raise AuthorizationException("Можна шукати матчі лише для себе")
    match_service = MatchService()  # Створення екземпляра MatchService
    return await match_service.find_match_service(
        request_data.user_id, current_user, db, background_tasks
    )

@router.post(
    "/accept",
    summary="Прийняти матч",
    description="Приймає очікуючий матч для автентифікованого користувача.",
)
async def accept_match(
    request_data: AcceptMatchRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на прийняття матчу для ID: {request_data.match_id}")
    if str(request_data.user_id) != str(current_user.id):
        match_logger.warning(
            f"Несанкціонований запит на прийняття: {request_data.user_id} != {current_user.id}"
        )
        raise AuthorizationException("Можна приймати матчі лише для себе")
    match_service = MatchService()  # Створення екземпляра MatchService
    return await match_service.accept_match_service(
        str(request_data.match_id), str(current_user.id), db
    )

@router.post(
    "/decline/{match_id}",
    summary="Відхилити матч",
    description="Відхиляє очікуючий матч для автентифікованого користувача.",
)
async def decline_match(
    match_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на відхилення матчу для ID: {match_id}")
    match_service = MatchService()  # Створення екземпляра MatchService
    return await match_service.decline_match_service(
        str(match_id), str(current_user.id), db
    )

@router.get(
    "/active",
    summary="Отримати активний матч",
    description="Повертає активний або очікуючий матч для автентифікованого користувача.",
)
async def get_active_match(
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на активний матч для користувача ID: {current_user.id}")
    match_service = MatchService()  # Створення екземпляра MatchService
    return await match_service.get_active_match_service(db, str(current_user.id))

@router.get(
    "/history",
    summary="Отримати історію матчів",
    description="Повертає історію матчів автентифікованого користувача з пагінацією.",
)
async def get_match_history(
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на історію матчів для користувача ID: {current_user.id}")
    match_service = MatchService()  # Створення екземпляра MatchService
    return await match_service.get_match_history_service(
        str(current_user.id), limit, offset, db
    )

@router.get(
    "/details/{match_id}",
    summary="Отримати деталі матчу",
    description="Повертає деталі конкретного матчу, якщо користувач є учасником.",
)
async def get_match_details(
    match_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на деталі матчу для ID: {match_id}")
    match_service = MatchService()  # Створення екземпляра MatchService
    match = await match_service.get_match_details_service(db, str(match_id))
    if str(current_user.id) not in [str(match.player1_id), str(match.player2_id)]:
        match_logger.warning(
            f"Несанкціонований запит на деталі: {current_user.id} не в матчі {match_id}"
        )
        raise AuthorizationException("Ви не є учасником цього матчу")
    return match

@router.post(
    "/complete/{match_id}",
    summary="Завершити матч",
    description="Позначає матч як завершений із вказаним переможцем, якщо користувач є учасником.",
)
async def complete_match(
    match_id: UUID4,
    winner_id: UUID4,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на завершення матчу для ID: {match_id}")
    match_service = MatchService()  # Створення екземпляра MatchService
    match = await match_service.get_match_details_service(db, str(match_id))
    if str(current_user.id) not in [str(match.player1_id), str(match.player2_id)]:
        match_logger.warning(
            f"Несанкціонований запит на завершення: {current_user.id} не в матчі {match_id}"
        )
        raise AuthorizationException("Ви не є учасником цього матчу")
    return await match_service.complete_match_service(str(winner_id), db, str(match_id))

@router.post(
    "/capitulate",
    summary="Капітулювати в матчі",
    description="Дозволяє користувачу здатися в матчі, оголошуючи опонента переможцем.",
)
async def capitulate_match(
    request: CapitulateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на капітуляцію для матчу ID: {request.match_id}")
    if str(request.loser_id) != str(current_user.id):
        match_logger.warning(
            f"Несанкціонований запит на капітуляцію: {request.loser_id} != {current_user.id}"
        )
        raise AuthorizationException("Можна капітулювати лише від свого імені")
    match_service = MatchService()  # Створення екземпляра MatchService
    await match_service.capitulate_match_logic(request.match_id, request.loser_id)
    return {"message": "Матч успішно капітульовано"}

@router.post(
    "/cancel_find",
    summary="Скасувати пошук матчу",
    description="Видаляє автентифікованого користувача з черги підбору матчів.",
)
async def cancel_find_match(
    current_user: UserBaseResponse = Depends(get_current_user),
):
    match_logger.info(f"Запит на скасування пошуку матчу для користувача ID: {current_user.id}")
    match_service = MatchService()  # ВИПРАВЛЕНО: Створення екземпляра MatchService
    return await match_service.cancel_find_match_service(str(current_user.id))

@router.websocket("/ws/{user_id}", name="Повідомлення про матчі")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: UUID4,
    token_data: dict = Depends(AccessTokenFromWebSocket()),
):
    if str(user_id) != token_data["user"]["id"]:
        match_logger.warning(
            f"Несанкціоноване підключення WebSocket: {user_id} != {token_data['user']['id']}"
        )
        await websocket.close(code=1008, reason="Несанкціоновано")
        return

    match_logger.info(f"Підключення WebSocket для користувача ID: {user_id}")
    await manager.connect(websocket, str(user_id))
    try:
        while True:
            data = await websocket.receive_text()
            match_logger.debug(f"Отримано повідомлення від користувача {user_id}: {data}")
    except WebSocketDisconnect:
        match_logger.info(f"WebSocket відключено для користувача ID: {user_id}")
        manager.disconnect(websocket, str(user_id))
    except Exception as e:
        match_logger.error(f"Помилка WebSocket для користувача {user_id}: {str(e)}")
        if websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason=f"Внутрішня помилка сервера: {str(e)}")