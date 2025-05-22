import json
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID as UUID4, uuid4

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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

class MatchService:
    QUEUE_KEY = "matchmaking_queue"
    match_acceptance_timeout = 30  # Seconds for match acceptance
    match_draw_timeout = 300  # Seconds for match draw timeout

    def __init__(self, redis_client: RedisClient = None):
        self.redis_client = redis_client or get_redis_client()

    async def add_player_to_queue(self, user_id: UUID4, rating: int) -> bool:
        """
        Add a player to the matchmaking queue with their rating.
        """
        entry = PlayerQueueEntry(
            user_id=user_id, rating=rating, timestamp=datetime.now()
        )
        key = f"{self.QUEUE_KEY}:{entry.rating}"
        await self.redis_client.zadd(
            key, {entry.model_dump_json(): entry.timestamp.timestamp()}
        )
        return True

    async def has_active_match(self, db: AsyncSession, user_id: str) -> bool:
        """
        Check if the user has an active or pending match.
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
        Find a match for a user.
        """
        user_uuid = UUID4(user_id)
        if user_uuid != current_user.id:
            raise AuthorizationException("You can only find matches for yourself")
        user = await get_user_by_id(db, user_uuid)
        if not user:
            raise ResourceNotFoundException("User not found")
        if await self.has_active_match(db, user_id):
            raise BadRequestException("User already has an active match")
        added = await self.add_player_to_queue(user.id, user.rating)
        if not added:
            raise BadRequestException("Player already in queue")
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
        """
        Process the matchmaking queue to pair players.
        """
        rating_range = 100  # Match players within ±100 rating points
        matched_pairs = set()  # Track matched user IDs to avoid duplicates

        rating_min = 0  # Minimum rating
        rating_max = 5000  # Maximum rating
        for rating in range(rating_min, rating_max + 1, 50):  # Step by 50
            key = f"{self.QUEUE_KEY}:{rating}"
            # Fetch all entries in the sorted set
            entry_jsons = await self.redis_client.zrange(key, 0, -1)
            if not entry_jsons:
                continue

            for entry_json in entry_jsons:
                try:
                    entry = PlayerQueueEntry.model_validate_json(entry_json)
                    if str(entry.user_id) in matched_pairs:
                        continue

                    # Get the score (timestamp) for this entry
                    timestamp = await self.redis_client.zscore(key, entry_json)
                    if timestamp is None:
                        await self.redis_client.zrem(key, entry_json)
                        continue

                    entry_time = datetime.fromtimestamp(timestamp)
                    if datetime.now() - entry_time > timedelta(minutes=5):
                        await self.redis_client.zrem(key, entry_json)
                        continue

                    for offset in range(-rating_range, rating_range + 1, 50):
                        match_key = f"{self.QUEUE_KEY}:{rating + offset}"
                        match_entry_jsons = await self.redis_client.zrange(
                            match_key, 0, -1
                        )
                        for match_json in match_entry_jsons:
                            try:
                                match_entry = PlayerQueueEntry.model_validate_json(
                                    match_json
                                )
                                if (
                                    str(match_entry.user_id) in matched_pairs
                                    or match_entry.user_id == entry.user_id
                                ):
                                    continue

                                if await self.has_active_match(
                                    db, str(entry.user_id)
                                ) or await self.has_active_match(
                                    db, str(match_entry.user_id)
                                ):
                                    continue

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

                                await self.redis_client.zrem(key, entry_json)
                                await self.redis_client.zrem(match_key, match_json)

                                matched_pairs.add(str(entry.user_id))
                                matched_pairs.add(str(match_entry.user_id))

                                notification = {
                                    "match_id": str(new_match.id),
                                    "status": "pending",
                                    "opponent_id": str(new_match.player2_id),
                                    "timeout": acceptance_timeout,
                                }
                                await manager.send_personal_message(
                                    notification, str(new_match.player1_id)
                                )
                                notification["opponent_id"] = str(new_match.player1_id)
                                await manager.send_personal_message(
                                    notification, str(new_match.player2_id)
                                )
                                break
                            except Exception as e:
                                print(f"Error processing match entry: {e}")
                                continue
                        if str(entry.user_id) in matched_pairs:
                            break
                except Exception as e:
                    print(f"Error processing queue entry: {e}")
                    continue

    async def accept_match_service(self, match_id: str, user_id: str, db: AsyncSession):
        """
        Accept a pending match.
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
        Decline a pending match.
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

    async def get_active_match_service(self, db: AsyncSession) -> Optional[MatchResponse]:
        """
        Get the active or pending match for the user.
        """
        match = await get_active_or_pending_match(db, None)  # Needs user_id from context
        if not match:
            return None
        return MatchResponse.from_orm(match)

    async def get_match_history_service(
        self, limit: int, offset: int, db: AsyncSession
    ) -> List[MatchResponse]:
        """
        Get match history for the user with pagination.
        """
        matches = await get_match_history(db, None, limit, offset)  # Needs user_id
        return [MatchResponse.from_orm(match) for match in matches]

    async def get_match_details_service(self, db: AsyncSession, match_id: str) -> Match:
        """
        Get details of a specific match.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        return match

    async def complete_match_service(self, winner_id: str, db: AsyncSession, match_id: str):
        """
        Mark a match as completed with the specified winner.
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
        Handle match capitulation, declaring the opponent as the winner.
        """
        # Placeholder: Implement logic to update match with loser and winner
        pass

    async def cancel_find_match_service(self, user_id: str):
        """
        Remove the user from the matchmaking queue.
        """
        user_uuid = UUID4(user_id)
        # Since we don't know the user's rating, check all possible rating keys
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
                except Exception as e:
                    print(f"Error processing queue entry for removal: {e}")
                    continue
        return {"message": "User removed from queue" if removed else "User not found in queue"}