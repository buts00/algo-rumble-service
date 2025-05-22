from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID as UUID4, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
import logging
from src.data.repositories import RedisClient, get_redis_client
from src.data.schemas import Match, User
from src.data.repositories.match_repository import (
    get_active_or_pending_match,
    get_match_by_id,
    get_match_history,
)
from src.data.repositories.user_repository import get_user_by_id
from src.data.schemas.match import PlayerQueueEntry, MatchResponse
from src.data.schemas import UserBaseResponse
from src.errors import (
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from src.presentation.websocket import manager

logger = logging.getLogger("app.match")

class MatchService:
    QUEUE_KEY = "matchmaking_queue"
    match_acceptance_timeout = 30  # Seconds for match acceptance
    match_draw_timeout = 300  # Seconds for match draw timeout

    def __init__(self, redis_client: RedisClient = None):
        self.redis_client = redis_client or get_redis_client()

    async def add_player_to_queue(self, user_id: UUID4, rating: int) -> bool:
        """
        Додає гравця до черги підбору матчів з його рейтингом.
        """
        entry = PlayerQueueEntry(
            user_id=user_id, rating=rating, timestamp=datetime.now()
        )
        key = f"{self.QUEUE_KEY}:{entry.rating}"
        await self.redis_client.zadd(
            key, {entry.model_dump_json(): entry.timestamp.timestamp()}
        )
        logger.info(f"Added player {user_id} to queue at rating {rating}")
        return True

    async def has_active_match(self, db: AsyncSession, user_id: str) -> bool:
        """
        Перевіряє, чи має користувач активний або очікуючий матч.
        """
        match = await get_active_or_pending_match(db, user_id)
        return match is not None

    async def find_match_service(
        self,
        user_id: str,
        current_user: UserBaseResponse,
        db: AsyncSession,
        background_tasks,
    ):
        """
        Знайти матч для користувача.
        """
        user_uuid = UUID4(user_id)
        if user_uuid != current_user.id:
            logger.warning(f"Unauthorized match request: {user_id} != {current_user.id}")
            raise AuthorizationException("You can only find matches for yourself")
        user = await get_user_by_id(db, user_uuid)
        if not user:
            raise ResourceNotFoundException("User not found")
        if await self.has_active_match(db, user_id):
            raise BadRequestException("User already has an active match")
        added = await self.add_player_to_queue(user.id, user.rating)
        if not added:
            raise BadRequestException("Player already in queue")
        logger.info(f"Scheduling process_match_queue for user {user_id}")
        background_tasks.add_task(
            self.process_match_queue,
            db,
            self.match_acceptance_timeout,
            self.match_draw_timeout,
        )
        return {"message": "Player added to queue"}

    async def process_match_queue(
        self, db: AsyncSession, acceptance_timeout: int, draw_timeout: int
    ):
        """Обробляє чергу підбору матчів для створення пар."""
        logger.info("Початок process_match_queue")
        rating_range = 200  # Підбір гравців у межах ±200 рейтингових очок
        matched_pairs = set()  # Відстеження парного підбору для уникнення дублювання

        rating_min = 0  # Мінімальний рейтинг
        rating_max = 5000  # Максимальний рейтинг
        for rating in range(rating_min, rating_max + 1, 50):  # Крок 50
            key = f"{self.QUEUE_KEY}:{rating}"
            try:
                entries = await self.redis_client.zrange(key, 0, -1)
                logger.info(f"Отримано {len(entries)} записів для рейтингу {rating}: {entries}")
            except Exception as e:
                logger.error(f"Помилка при отриманні записів черги для рейтингу {rating}: {e}")
                continue

            if not entries:
                continue

            for entry_json in entries:
                try:
                    entry = PlayerQueueEntry.model_validate_json(entry_json)
                    logger.info(f"Обробка запису для користувача {entry.user_id}, рейтинг {entry.rating}")
                    if str(entry.user_id) in matched_pairs:
                        logger.info(f"Пропуск уже підібраного користувача {entry.user_id}")
                        continue

                    for offset in range(-rating_range, rating_range + 1, 50):
                        match_key = f"{self.QUEUE_KEY}:{rating + offset}"
                        try:
                            match_entries = await self.redis_client.zrange(match_key, 0, -1)
                            logger.info(f"Отримано {len(match_entries)} записів для рейтингу {rating + offset}")
                        except Exception as e:
                            logger.error(f"Помилка при отриманні записів черги для рейтингу {rating + offset}: {e}")
                            continue

                        for match_json in match_entries:
                            try:
                                match_entry = PlayerQueueEntry.model_validate_json(match_json)
                                logger.info(f"Перевірка потенційного матчу: користувач {match_entry.user_id}, рейтинг {match_entry.rating}")
                                if (
                                    str(match_entry.user_id) in matched_pairs
                                    or match_entry.user_id == entry.user_id
                                ):
                                    logger.info(f"Пропуск невалідного матчу: користувач {match_entry.user_id}")
                                    continue

                                if await self.has_active_match(db, str(entry.user_id)) or await self.has_active_match(db, str(match_entry.user_id)):
                                    logger.info(f"Пропуск користувачів із активними матчами: {entry.user_id}, {match_entry.user_id}")
                                    continue

                                logger.info(f"Створення матчу між {entry.user_id} і {match_entry.user_id}")
                                new_match = Match(
                                    id=uuid4(),
                                    player1_id=entry.user_id,
                                    player2_id=match_entry.user_id,
                                    status="pending",
                                    created_at=datetime.now(),
                                    rating1=entry.rating,
                                    rating2=match_entry.rating,
                                )
                                db.add(new_match)
                                await db.commit()
                                logger.info(f"Матч створено: ID {new_match.id}")

                                await self.redis_client.zrem(key, entry_json)
                                await self.redis_client.zrem(match_key, match_json)
                                logger.info(f"Видалено підібрані записи з Redis")

                                matched_pairs.add(str(entry.user_id))
                                matched_pairs.add(str(match_entry.user_id))

                                notification = {
                                    "match_id": str(new_match.id),
                                    "status": "pending",
                                    "opponent_id": str(new_match.player2_id),
                                    "timeout": acceptance_timeout,
                                }
                                try:
                                    await manager.send_match_notification(str(new_match.player1_id), notification)
                                    logger.info(f"Надіслано повідомлення гравцеві 1: {new_match.player1_id}")
                                except Exception as e:
                                    logger.error(f"Помилка WebSocket для гравця 1: {e}")
                                notification["opponent_id"] = str(new_match.player1_id)
                                try:
                                    await manager.send_match_notification(str(new_match.player2_id), notification)
                                    logger.info(f"Надіслано повідомлення гравцеві 2: {new_match.player2_id}")
                                except Exception as e:
                                    logger.error(f"Помилка WebSocket для гравця 2: {e}")
                                break
                            except Exception as e:
                                logger.error(f"Помилка обробки запису матчу: {e}")
                                continue
                    if str(entry.user_id) in matched_pairs:
                        break
                except Exception as e:
                    logger.error(f"Помилка обробки запису черги: {e}")
                    continue
        logger.info("Завершено process_match_queue")

    async def accept_match_service(self, match_id: str, user_id: str, db: AsyncSession):
        """
        Прийняти очікуючий матч.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if str(user_id) not in [str(match.player1_id), str(match.player2_id)]:
            raise AuthorizationException("Not a participant in this match")
        if match.status != "pending":
            raise BadRequestException("Match is not in pending state")
        match.status = "active"
        await db.commit()
        return {"message": "Match accepted"}

    async def decline_match_service(self, match_id: str, user_id: str, db: AsyncSession):
        """
        Відхилити очікуючий матч.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if str(user_id) not in [str(match.player1_id), str(match.player2_id)]:
            raise AuthorizationException("Not a participant in this match")
        if match.status != "pending":
            raise BadRequestException("Match is not in pending state")
        await db.delete(match)
        await db.commit()
        return {"message": "Match declined"}

    async def get_active_match_service(self, db: AsyncSession, user_id: str) -> Optional[MatchResponse]:
        """
        Отримати активний або очікуючий матч для користувача.
        """
        match = await get_active_or_pending_match(db, user_id)
        return MatchResponse.from_orm(match) if match else None

    async def get_match_history_service(
        self, user_id: str, limit: int, offset: int, db: AsyncSession
    ) -> List[MatchResponse]:
        """
        Отримати історію матчів для користувача з пагінацією.
        """
        matches = await get_match_history(db, user_id, limit, offset)
        return [MatchResponse.from_orm(match) for match in matches]

    async def get_match_details_service(self, db: AsyncSession, match_id: str) -> Match:
        """
        Отримати деталі конкретного матчу.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        return match

    async def complete_match_service(self, winner_id: str, db: AsyncSession, match_id: str):
        """
        Позначити матч як завершений із вказаним переможцем.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if match.status != "active":
            raise BadRequestException("Match is not active")
        match.winner_id = UUID4(winner_id)
        match.status = "completed"
        await db.commit()
        return {"message": "Match completed"}

    async def capitulate_match_logic(self, match_id: UUID4, loser_id: UUID4):
        """
        Обробити капітуляцію матчу, оголосивши опонента переможцем.
        """
        # Placeholder: Реалізувати логіку оновлення матчу з переможцем і переможеним
        pass

    async def cancel_find_match_service(self, user_id: str):
        """
        Видалити користувача з черги підбору матчів.
        """
        user_uuid = UUID4(user_id)
        rating_min = 0
        rating_max = 5000
        removed = False
        for rating in range(rating_min, rating_max + 1, 50):
            key = f"{self.QUEUE_KEY}:{rating}"
            entries = await self.redis_client.zrange(key, 0, -1)
            for entry_json in entries:
                try:
                    entry = PlayerQueueEntry.model_validate_json(entry_json)
                    if entry.user_id == user_uuid:
                        await self.redis_client.zrem(key, entry_json)
                        removed = True
                        logger.info(f"Removed user {user_id} from queue at rating {rating}")
                except Exception as e:
                    logger.error(f"Error processing queue entry for removal: {e}")
                    continue
        return {"message": "User removed from queue" if removed else "User not found in queue"}