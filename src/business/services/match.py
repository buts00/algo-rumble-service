import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic.v1 import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import logger
from src.data.repositories import RedisClient, get_redis_client
from src.data.repositories.match_repository import (
    create_match,
    finish_match_with_winner,
    get_active_or_pending_match,
    get_expired_pending_matches,
    get_match_by_id,
    get_match_history,
    select_problem_for_match,
)
from src.data.repositories.user_repository import get_users_by_ids, get_user_by_id
from src.data.schemas import User
from src.data.schemas.match import Match, MatchStatus, PlayerQueueEntry
from src.errors import AuthorizationException, BadRequestException, ResourceNotFoundException
from src.presentation.websocket import manager

# Create a module-specific logger
match_logger = logger.getChild("match")


class MatchService:
    QUEUE_KEY = "matchmaking_queue"

    def __init__(self, redis_client: RedisClient = None):
        self.redis_client = redis_client or get_redis_client()

    async def add_player_to_queue(self, user_id: uuid.UUID, rating: int) -> bool:
        """
        Add a player to the matchmaking queue in Redis.
        Returns True if added, False if already in queue.
        """
        entry = PlayerQueueEntry(
            user_id=user_id, rating=rating, timestamp=datetime.now(timezone.utc)
        )
        # Check if user is already in queue
        existing = await self.redis_client.get(f"queue:user:{user_id}")
        if existing:
            match_logger.info(f"Player {user_id} is already in the queue.")
            return False

        # Add to Redis sorted a set (score is timestamp)
        await self.redis_client.zadd(
            self.QUEUE_KEY, {json.dumps(entry.model_dump()): entry.timestamp.timestamp()}
        )
        await self.redis_client.set(
            f"queue:user:{user_id}", "1", ex=3600
        )  # Expire in 1 hour
        match_logger.info(f"Player {user_id} added to queue.")
        return True

    async def remove_player_from_queue(self, user_id: uuid.UUID) -> bool:
        """
        Remove a player from the matchmaking queue in Redis.
        Returns True if removed, False if not found.
        """
        # Check if user is in queue
        exists = await self.redis_client.get(f"queue:user:{user_id}")
        if not exists:
            match_logger.info(f"Player {user_id} not found in queue for removal.")
            return False

        # Remove from sorted set and user flag
        queue_entries = await self.redis_client.zrange(self.QUEUE_KEY, 0, -1)
        for entry_json in queue_entries:
            entry = PlayerQueueEntry(**json.loads(entry_json))
            if entry.user_id == user_id:
                await self.redis_client.zrem(self.QUEUE_KEY, entry_json)
                break
        await self.redis_client.delete(f"queue:user:{user_id}")
        match_logger.info(f"Player {user_id} removed from queue.")
        return True

    async def process_match_queue(
        self,
        db: AsyncSession,
        match_acceptance_timeout_cb=None,
        match_draw_timeout_cb=None,
    ) -> List[Match]:
        """
        Process the matchmaking queue to create matches between players.
        Returns list of created matches.
        """
        queue_entries = await self.redis_client.zrange(self.QUEUE_KEY, 0, -1)
        if len(queue_entries) < 2:
            return []
        match_logger.info(f"Processing match queue. Queue size: {len(queue_entries)}")
        players = [PlayerQueueEntry(**json.loads(entry)) for entry in queue_entries]
        players.sort(key=lambda x: x.timestamp)
        created_matches = []
        i = 0
        while i < len(players) - 1:
            player1 = players[i]
            best_match_idx = -1
            min_rating_diff = float("inf")
            for j in range(i + 1, len(players)):
                player2 = players[j]
                rating_diff = abs(player1.rating - player2.rating)
                if rating_diff < min_rating_diff:
                    min_rating_diff = rating_diff
                    best_match_idx = j
            if best_match_idx != -1:
                player2 = players[best_match_idx]
                try:
                    problem_id = await select_problem_for_match(
                        db, player1.rating, player2.rating
                    )
                    new_match = Match(
                        player1_id=player1.user_id,
                        player2_id=player2.user_id,
                        problem_id=problem_id,
                        status=MatchStatus.PENDING,
                        start_time=datetime.now(timezone.utc),
                    )
                    new_match = await create_match(db, new_match)
                    match_logger.info(
                        f"Match created: {new_match.id} between players {player1.user_id} and {player2.user_id}"
                    )
                    users = await get_users_by_ids(
                        db, [player1.user_id, player2.user_id]
                    )
                    user_map = {u.id: u for u in users}
                    user1 = user_map.get(player1.user_id)
                    user2 = user_map.get(player2.user_id)
                    await self.send_match_notification(
                        str(player1.user_id),
                        {
                            "status": "match_found",
                            "match_id": str(new_match.id),
                            "opponent_username": user2.username if user2 else "",
                            "problem_id": str(problem_id) if problem_id else None,
                        },
                    )
                    await self.send_match_notification(
                        str(player2.user_id),
                        {
                            "status": "match_found",
                            "match_id": str(new_match.id),
                            "opponent_username": user1.username if user1 else "",
                            "problem_id": str(problem_id) if problem_id else None,
                        },
                    )
                    if match_acceptance_timeout_cb:
                        asyncio.create_task(
                            match_acceptance_timeout_cb(str(new_match.id), db)
                        )
                    if match_draw_timeout_cb:
                        asyncio.create_task(
                            match_draw_timeout_cb(str(new_match.id), db)
                        )
                    # Remove players from Redis queue
                    await self.redis_client.zrem(
                        self.QUEUE_KEY, json.dumps(player1.model_dump())
                    )
                    await self.redis_client.zrem(
                        self.QUEUE_KEY, json.dumps(player2.model_dump())
                    )
                    await self.redis_client.delete(f"queue:user:{player1.user_id}")
                    await self.redis_client.delete(f"queue:user:{player1.user_id}")
                    await self.redis_client.delete(f"queue:user:{player2.user_id}")
                    created_matches.append(new_match)
                except Exception as e:
                    match_logger.error(f"Error creating match: {str(e)}")
                    i += 1
            else:
                i += 1
        return created_matches

    @staticmethod
    async def select_problem_for_match(
        db: AsyncSession, player1_rating: int, player2_rating: int
    ) -> Optional[uuid.UUID]:
        """
        Select a problem for a match based on player ratings.
        """
        match_logger.warning("This method is deprecated; use match_repository.select_problem_for_match instead.")
        return await select_problem_for_match(db, player1_rating, player2_rating)

    @staticmethod
    async def send_match_notification(user_id: str, data: dict) -> None:
        """
        Send a match notification to a user.
        """
        try:
            await manager.send_match_notification(user_id, data)
            match_logger.debug(f"Notification sent to user {user_id}: {data}")
        except Exception as e:
            match_logger.error(
                f"Error sending notification to user {user_id}: {str(e)}"
            )

    @staticmethod
    async def send_cancellation_notifications(
        match: Match, match_id: UUID4, reason: str
    ) -> None:
        """
        Send cancellation notifications to both players in a match.
        """
        try:
            data = {"status": "cancelled", "match_id": str(match_id), "reason": reason}
            await manager.send_match_notification(str(match.player1_id), data)
            await manager.send_match_notification(str(match.player2_id), data)
            match_logger.debug(
                f"Cancellation notifications sent for match {match_id} with reason: {reason}"
            )
        except Exception as e:
            match_logger.error(
                f"Error sending cancellation notifications for match {match_id}: {str(e)}"
            )

    async def cancel_expired_matches(self, db: AsyncSession) -> None:
        """
        Cancel matches that have been pending for too long.
        """
        try:
            expiry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
            pending_matches = await get_expired_pending_matches(db, expiry_time)
            for match in pending_matches:
                match.status = MatchStatus.CANCELLED
                match.end_time = datetime.now(timezone.utc)
                await self.send_cancellation_notifications(match, match.id, "timeout")
                db.add(match)
                match_logger.info(f"Cancelled expired match: {match.id}")
            await db.commit()
            match_logger.info(f"Cancelled {len(pending_matches)} expired matches")
        except Exception as e:
            match_logger.error(f"Error cancelling expired matches: {str(e)}")

    @staticmethod
    async def capitulate_match_logic(
        db: AsyncSession, match_id: UUID4, loser_id: UUID4
    ):
        """
        Handle match capitulation logic.
        """
        from src.business.services.match_rating import RatingService
        from src.presentation.routes.submission import submission_logger

        match = await get_match_by_id(db, match_id)
        if not match or match.status != MatchStatus.ACTIVE:
            raise ResourceNotFoundException("Match not found or not active")
        if match.player1_id == loser_id:
            winner_id = match.player2_id
        elif match.player2_id == loser_id:
            winner_id = match.player1_id
        else:
            raise AuthorizationException("Loser not in this match")
        await finish_match_with_winner(db, match_id, winner_id)
        users = await get_users_by_ids(db, [match.player1_id, match.player2_id])
        user_map = {u.id: u for u in users}
        winner = user_map.get(winner_id)
        loser = user_map.get(loser_id)
        old_winner_rating = winner.rating
        old_loser_rating = loser.rating
        if not winner or not loser:
            raise ResourceNotFoundException("Could not load player data")
        await RatingService.update_ratings_after_match(db, winner.id, loser.id)
        await manager.send_match_notification(
            str(winner.id),
            {
                "status": "match_completed",
                "match_id": str(match.id),
                "message": "Congratulations! You won the match as your opponent surrendered.",
                "problem_id": str(match.problem_id),
                "result": "win",
                "new_rating": winner.rating,
                "old_rating": old_winner_rating,
            },
        )
        await manager.send_match_notification(
            str(loser.id),
            {
                "status": "match_completed",
                "message": f"You surrendered the match. '{winner.username}' is declared the winner.",
                "match_id": str(match.id),
                "problem_id": str(match.problem_id),
                "result": "loss",
                "new_rating": loser.rating,
                "old_rating": old_loser_rating,
            },
        )
        submission_logger.info(
            f"Match completed via capitulation: ID {match_id}, Winner: {winner.username}"
        )

    @staticmethod
    async def send_accept_status(
        user_id: str, match_id: uuid.UUID, status: str
    ) -> None:
        """
        Send match acceptance status to a user.
        """
        try:
            data = {"status": status, "match_id": str(match_id)}
            await manager.send_match_notification(user_id, data)
            match_logger.info(
                f"Sent accept status {status} to user {user_id} for match {match_id}"
            )
        except Exception as e:
            match_logger.error(f"Failed to send accept status to {user_id}: {e}")

    async def match_acceptance_timeout(self, db: AsyncSession, match_id: UUID4) -> None:
        """
        Handle match acceptance timeout.
        """
        try:
            match = await get_match_by_id(db, match_id)
            if match and match.status == MatchStatus.PENDING:
                match.status = MatchStatus.CANCELLED
                match.end_time = datetime.now(timezone.utc)
                await self.send_cancellation_notifications(match, match_id, "timeout")
                await db.commit()
                match_logger.info(
                    f"Match {match_id} cancelled due to acceptance timeout"
                )
        except Exception as e:
            match_logger.error(
                f"Error in match acceptance timeout for match {match_id}: {e}"
            )

    async def match_draw_timeout(self, db: AsyncSession, match_id: UUID4) -> None:
        """
        Handle match draw timeout.
        """
        try:
            match = await get_match_by_id(db, match_id)
            if match and match.status == MatchStatus.ACTIVE:
                match.status = MatchStatus.COMPLETED
                match.end_time = datetime.now(timezone.utc)
                await db.commit()
                await self.send_match_notification(
                    str(match.player1_id), {"status": "draw", "match_id": str(match_id)}
                )
                await self.send_match_notification(
                    str(match.player2_id), {"status": "draw", "match_id": str(match_id)}
                )
                match_logger.info(f"Match {match_id} ended in a draw due to timeout")
        except Exception as e:
            match_logger.error(f"Error in match draw timeout for match {match_id}: {e}")

    async def find_match_service(
        self, user_id: str, current_user: User, db: AsyncSession, background_tasks
    ):
        """
        Find a match for a user.
        """
        user_uuid = uuid.UUID(user_id)
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

    async def accept_match_service(self, match_id: UUID4, user_id: str, db: AsyncSession):
        """
        Accept a match.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if match.status != MatchStatus.PENDING:
            raise BadRequestException("Match is not in pending state")
        if str(match.player1_id) != user_id and str(match.player2_id) != user_id:
            raise AuthorizationException("You are not a participant in this match")
        match.status = MatchStatus.ACTIVE
        await db.commit()
        await self.send_accept_status(str(match.player1_id), match_id, "accepted")
        await self.send_accept_status(str(match.player2_id), match_id, "accepted")
        return {"message": "Match accepted successfully"}

    async def decline_match_service(
        self, match_id: UUID4, user_id: UUID4, db: AsyncSession
    ):
        """
        Decline a match.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if match.status != MatchStatus.PENDING:
            raise BadRequestException("Match is not in pending state")
        if match.player1_id != user_id and match.player2_id != user_id:
            raise AuthorizationException("You are not a participant in this match")
        match.status = MatchStatus.CANCELLED
        match.end_time = datetime.now(timezone.utc)
        await self.send_cancellation_notifications(match, match_id, "declined")
        await db.commit()
        return {"message": "Match declined successfully"}

    @staticmethod
    async def get_active_match_service(user_id: str, db: AsyncSession):
        """
        Get active or pending match for a user.
        """
        match = await get_active_or_pending_match(db, user_id)
        if not match:
            raise ResourceNotFoundException("No active match found")
        return {
            "match_id": str(match.id),
            "status": match.status,
            "player1_id": str(match.player1_id),
            "player2_id": str(match.player2_id),
            "problem_id": str(match.problem_id) if match.problem_id else None,
        }

    @staticmethod
    async def get_match_history_service(
        user_id: str, limit: int, offset: int, db: AsyncSession
    ):
        """
        Get match history for a user.
        """
        matches = await get_match_history(db, user_id, limit, offset)
        return [
            {
                "match_id": str(match.id),
                "status": match.status,
                "player1_id": str(match.player1_id),
                "player2_id": str(match.player2_id),
                "problem_id": str(match.problem_id) if match.problem_id else None,
                "winner_id": str(match.winner_id) if match.winner_id else None,
            }
            for match in matches
        ]

    @staticmethod
    async def get_match_details_service(match_id: UUID4, db: AsyncSession):
        """
        Get details of a match.
        """
        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        return {
            "match_id": str(match.id),
            "status": match.status,
            "player1_id": str(match.player1_id),
            "player2_id": str(match.player2_id),
            "problem_id": str(match.problem_id) if match.problem_id else None,
            "winner_id": str(match.winner_id) if match.winner_id else None,
        }

    @staticmethod
    async def complete_match_service(
        match_id: UUID4, winner_id: UUID4, db: AsyncSession
    ):
        """
        Complete a match with a winner.
        """
        from src.business.services.match_rating import RatingService

        match = await get_match_by_id(db, match_id)
        if not match:
            raise ResourceNotFoundException("Match not found")
        if match.status != MatchStatus.ACTIVE:
            raise BadRequestException("Match is not active")
        if match.player1_id != winner_id and match.player2_id != winner_id:
            raise AuthorizationException("Winner is not a participant in this match")
        await finish_match_with_winner(db, match_id, winner_id)
        loser_id = (
            match.player2_id if match.player1_id == winner_id else match.player1_id
        )
        await RatingService.update_ratings_after_match(db, winner_id, loser_id)
        return {"message": "Match completed successfully"}

    async def cancel_find_match_service(self, user_id: str):
        """
        Cancel match search for a user.
        """
        removed = await self.remove_player_from_queue(uuid.UUID(user_id))
        if not removed:
            raise BadRequestException("Player not in queue")
        return {"message": "Match search cancelled successfully"}

    @staticmethod
    async def has_active_match(db: AsyncSession, user_id: str) -> bool:
        """
        Check if a user has an active or pending match.
        """
        match = await get_active_or_pending_match(db, user_id)
        return match is not None