import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Union
from uuid import UUID

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.match.models.match import Match, MatchStatus
from src.match.schemas.queue import MatchQueueResult, PlayerQueueEntry
from src.match.websocket import manager
from src.problem.models.problem import Problem
from src.problem.schemas.problem import ProblemSelectionParams

logger = logging.getLogger(__name__)

# In-memory queue for development/testing without Kafka
player_queue: List[PlayerQueueEntry] = []

# Match acceptance timeout in seconds
MATCH_ACCEPTANCE_TIMEOUT = 15


async def create_kafka_topics():
    """
    Create Kafka topics if they don't exist using the Kafka Admin API.
    This is called when the consumer starts, instead of at container startup.
    """
    try:
        topics_config = os.environ.get(
            "KAFKA_CREATE_TOPICS", "player_queue:3:1,match_events:3:1"
        )
        topics = topics_config.split(",")

        # Create admin client
        admin_client = AIOKafkaAdminClient(
            bootstrap_servers=f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}"
        )

        try:
            await admin_client.start()

            # Get existing topics
            existing_topics = await admin_client.list_topics()

            # Create new topic objects
            new_topics = []
            for topic_config in topics:
                parts = topic_config.split(":")
                topic_name = parts[0]
                partitions = int(parts[1]) if len(parts) >= 2 else 1
                replication = int(parts[2]) if len(parts) >= 3 else 1

                if topic_name not in existing_topics:
                    logger.info(f"Creating Kafka topic: {topic_name}")
                    new_topic = NewTopic(
                        name=topic_name,
                        num_partitions=partitions,
                        replication_factor=replication,
                    )
                    new_topics.append(new_topic)

            # Create topics if any new ones
            if new_topics:
                await admin_client.create_topics(new_topics)
                for topic in new_topics:
                    logger.info(f"Kafka topic created: {topic.name}")

        finally:
            await admin_client.close()

    except Exception as e:
        logger.error(f"Error creating Kafka topics: {e}")


async def add_player_to_queue(
    user_id: Union[UUID, int], rating: int
) -> MatchQueueResult:
    """
    Add a player to the match queue using Kafka. Converts UUID and datetime to string for JSON serialization.
    """
    entry = PlayerQueueEntry(user_id=user_id, rating=rating)
    # Convert entry to dict and ensure JSON serializable types
    entry_dict = entry.model_dump()
    entry_dict["user_id"] = str(entry_dict.get("user_id"))
    # Convert datetime fields if present
    if "timestamp" in entry_dict and isinstance(entry_dict["timestamp"], datetime):
        entry_dict["timestamp"] = entry_dict["timestamp"].isoformat()
    message = json.dumps(entry_dict).encode("utf-8")

    try:
        # Ensure the topic exists before sending messages
        logger.info(f"Creating Kafka topic: {Config.PLAYER_QUEUE_TOPIC}")
        await create_kafka_topics()

        producer = AIOKafkaProducer(
            bootstrap_servers=f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}"
        )
        await producer.start()
        try:
            await producer.send_and_wait(Config.PLAYER_QUEUE_TOPIC, message)
            return MatchQueueResult(
                success=True, message="Player added to queue successfully"
            )
        finally:
            await producer.stop()
    except Exception as e:
        logger.error(f"Error adding player to Kafka queue: {e}")
        # Fallback to in-memory queue
        player_queue.append(entry)
        logger.info(f"Added player {user_id} to in-memory queue (fallback)")
        return MatchQueueResult(
            success=True, message="Player added to in-memory queue (fallback)"
        )


async def send_match_notification(
    user_id: Union[UUID, int],
    match_id: Union[UUID, int],
    opponent_id: Union[UUID, int],
    status: str,
):
    # Ensure we use string keys for manager
    uid = str(user_id)
    msg = {
        "in_match": True,
        "match_id": str(match_id),
        "status": status,
        "opponent_id": str(opponent_id),
    }
    await manager.send_match_notification(uid, msg)


async def find_match_for_player(
    db: AsyncSession, user_id: Union[UUID, int], rating: int
) -> Optional[Match]:
    # Check existing match
    stmt = (
        select(Match)
        .where(
            ((Match.player1_id == user_id) | (Match.player2_id == user_id))
            & (
                (Match.status == MatchStatus.PENDING)
                | (Match.status == MatchStatus.ACTIVE)
            )
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing:
        logger.info(f"Player {user_id} already has an active or pending match")
        return None

    # In-memory queue matching using Elo-based rating range
    # For Elo, players within 400 points have a significant skill difference
    # (higher rated player has ~90% expected win probability)
    base_rating_range = 400

    # Start with a narrow range and gradually expand if no match is found
    # This helps ensure fair matches while not making players wait too long
    potential = []
    if player_queue:
        for current_range in [
            base_rating_range,
            base_rating_range * 1.5,
            base_rating_range * 2,
        ]:
            potential = [
                e
                for e in player_queue
                if e.user_id != user_id and abs(e.rating - rating) <= current_range
            ]
            if potential:
                # Sort by rating difference to get the closest match
                potential.sort(key=lambda x: abs(x.rating - rating))
                break

        # If no match found even with expanded range, use all available players
        if not potential:
            potential = [e for e in player_queue if e.user_id != user_id]
            potential.sort(key=lambda x: abs(x.rating - rating))

        if potential:
            opponent = potential[0]
            # Check opponent existing match
            stmt2 = (
                select(Match)
                .where(
                    (
                        (Match.player1_id == opponent.user_id)
                        | (Match.player2_id == opponent.user_id)
                    )
                    & (
                        (Match.status == MatchStatus.PENDING)
                        | (Match.status == MatchStatus.ACTIVE)
                    )
                )
                .limit(1)
            )
            res2 = await db.execute(stmt2)
            opp_match = res2.scalars().first()
            if opp_match:
                logger.info(f"Opponent {opponent.user_id} busy, removing from queue")
                player_queue.remove(opponent)
                return None

            # Remove and create new match
            player_queue.remove(opponent)

            # Select an appropriate problem for the match
            problem_params = ProblemSelectionParams(
                player1_rating=rating, player2_rating=opponent.rating
            )

            selected_problem = await select_problem_for_match(db, problem_params)
            problem_id = selected_problem.id if selected_problem else None

            new_match = Match(
                player1_id=user_id,
                player2_id=opponent.user_id,
                problem_id=problem_id,
                status=MatchStatus.PENDING,
                start_time=datetime.utcnow(),
            )
            db.add(new_match)
            await db.commit()
            await db.refresh(new_match)

            if problem_id:
                logger.info(
                    f"Assigned problem ID {problem_id} to match ID {new_match.id}"
                )
            else:
                logger.warning(f"No problem assigned to match ID {new_match.id}")

            # Notify both players
            await send_match_notification(
                user_id, new_match.id, opponent.user_id, new_match.status
            )
            await send_match_notification(
                opponent.user_id, new_match.id, user_id, new_match.status
            )
            return new_match

    return None


async def check_match_timeouts(db: AsyncSession) -> int:
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=MATCH_ACCEPTANCE_TIMEOUT)

    stmt = select(Match).where(
        (Match.status == MatchStatus.PENDING) & (Match.start_time < threshold)
    )
    result = await db.execute(stmt)
    timed_out = result.scalars().all()

    for m in timed_out:
        m.status = MatchStatus.DECLINED
        m.end_time = now
        logger.info(f"Match {m.id} automatically declined due to timeout")

    if timed_out:
        await db.commit()
    return len(timed_out)


async def select_problem_for_match(
    db: AsyncSession, params: ProblemSelectionParams
) -> Optional[Problem]:
    """
    Select an appropriate problem for a match based on player ratings.

    Args:
        db: Database session
        params: Parameters for problem selection including player ratings

    Returns:
        A Problem object or None if no suitable problem is found
    """
    # Calculate target rating based on average of player ratings
    avg_rating = (params.player1_rating + params.player2_rating) // 2

    # Define acceptable rating range (within 200 points of average)
    # This ensures the problem is neither too easy nor too hard for both players
    min_rating = avg_rating - 200
    max_rating = avg_rating + 200

    logger.info(
        f"Selecting problem for match: Player ratings {params.player1_rating} and {params.player2_rating}, "
        f"Target rating range: {min_rating}-{max_rating}"
    )

    # Build query
    query = select(Problem).where(
        Problem.rating >= min_rating, Problem.rating <= max_rating
    )

    # Add topic filter if preferred topics are specified
    if params.preferred_topics:
        # This is a simplification - actual implementation would depend on how
        # the database handles array containment checks
        # For PostgreSQL, you might use the && operator (array overlap)
        logger.info(f"Filtering by preferred topics: {params.preferred_topics}")
        # This is a placeholder - implement based on your database
        # query = query.where(Problem.topics.overlap(params.preferred_topics))

    # Exclude problems that have been seen before
    if params.exclude_problem_ids:
        logger.info(f"Excluding problem IDs: {params.exclude_problem_ids}")
        query = query.where(Problem.id.notin_(params.exclude_problem_ids))

    # Order by how close the problem rating is to the average player rating
    # and limit to 10 candidates
    query = query.order_by(
        # Use abs() function to find problems closest to target rating
        # This is a simplification - implement based on your database
        # func.abs(Problem.rating - avg_rating)
    ).limit(10)

    try:
        result = await db.execute(query)
        problems = result.scalars().all()

        if not problems:
            logger.warning(
                f"No suitable problems found in rating range {min_rating}-{max_rating}"
            )
            # Fallback: get any problem regardless of rating
            fallback_query = select(Problem)
            if params.exclude_problem_ids:
                fallback_query = fallback_query.where(
                    Problem.id.notin_(params.exclude_problem_ids)
                )
            fallback_query = fallback_query.limit(1)

            fallback_result = await db.execute(fallback_query)
            problems = fallback_result.scalars().all()

            if not problems:
                logger.error("No problems found in the database")
                return None

        # If multiple problems match criteria, select one randomly
        # In a real implementation, you might want to use a more sophisticated
        # selection algorithm
        import random

        selected_problem = random.choice(problems)

        logger.info(
            f"Selected problem ID {selected_problem.id} with rating {selected_problem.rating} "
            f"for match with average player rating {avg_rating}"
        )

        return selected_problem
    except Exception as e:
        logger.error(f"Error selecting problem for match: {e}")
        return None


async def process_match_queue(db: AsyncSession):
    # Decline timed-out matches first
    timed_out_count = await check_match_timeouts(db)
    if timed_out_count > 0:
        logger.info(f"Automatically declined {timed_out_count} matches")

    await create_kafka_topics()

    try:
        consumer = AIOKafkaConsumer(
            Config.PLAYER_QUEUE_TOPIC,
            bootstrap_servers=f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}",
            group_id="match_processor",
            auto_offset_reset="earliest",
        )
        await consumer.start()
        try:
            async for message in consumer:
                data = json.loads(message.value.decode("utf-8"))
                entry = PlayerQueueEntry(**data)
                logger.info(f"Processing queued player {entry.user_id}")
                match = await find_match_for_player(db, entry.user_id, entry.rating)
                if match:
                    logger.info(
                        f"Created match {match.id} between {match.player1_id} and {match.player2_id}"
                    )
                else:
                    player_queue.append(entry)
                    logger.info(
                        f"No match for player {entry.user_id}, re-queued in memory"
                    )
        finally:
            await consumer.stop()
    except Exception as e:
        logger.error(f"Error starting Kafka consumer: {e}")
        logger.info("Fallback: process in-memory queue")
        processed = set()
        for entry in sorted(player_queue, key=lambda x: x.timestamp):
            if entry.user_id in processed:
                continue
            match = await find_match_for_player(db, entry.user_id, entry.rating)
            if match:
                processed.add(entry.user_id)
                processed.add(match.player2_id)
                logger.info(f"Created match {match.id} in fallback processing")
