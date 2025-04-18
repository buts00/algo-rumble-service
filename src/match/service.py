import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from sqlalchemy.orm import Session

from src.config import Config
from src.match.models.match import Match, MatchStatus
from src.match.schemas.queue import PlayerQueueEntry, MatchQueueResult
from src.match.websocket import manager

logger = logging.getLogger(__name__)

# In-memory queue for development/testing without Kafka
player_queue: List[PlayerQueueEntry] = []

# Match acceptance timeout in seconds
MATCH_ACCEPTANCE_TIMEOUT = 15


def create_kafka_topics():
    """
    Create Kafka topics if they don't exist.
    This is called when the consumer starts, instead of at container startup.
    """
    try:
        # Get topic configuration from environment variables
        topics_config = os.environ.get(
            "KAFKA_CREATE_TOPICS", "player_queue:3:1,match_events:3:1"
        )

        # Parse topic configuration
        topics = topics_config.split(",")

        for topic_config in topics:
            parts = topic_config.split(":")
            if len(parts) >= 1:
                topic_name = parts[0]
                partitions = parts[1] if len(parts) >= 2 else "1"
                replication = parts[2] if len(parts) >= 3 else "1"

                # Create topic using kafka-topics.sh
                cmd = [
                    "/opt/bitnami/kafka/bin/kafka-topics.sh",
                    "--create",
                    "--if-not-exists",
                    "--bootstrap-server",
                    f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}",
                    "--topic",
                    topic_name,
                    "--partitions",
                    partitions,
                    "--replication-factor",
                    replication,
                ]

                logger.info(f"Creating Kafka topic: {topic_name}")
                subprocess.run(cmd, check=True)
                logger.info(f"Kafka topic created: {topic_name}")

    except Exception as e:
        logger.error(f"Error creating Kafka topics: {str(e)}")
        # Continue even if topic creation fails, as topics might already exist


async def add_player_to_queue(user_id: int, rating: int) -> MatchQueueResult:
    """
    Add a player to the match queue using Kafka.
    """
    try:
        # Create a player queue entry
        entry = PlayerQueueEntry(user_id=user_id, rating=rating)

        # Serialize the entry to JSON
        message = json.dumps(entry.model_dump()).encode("utf-8")

        # Create a Kafka producer
        producer = AIOKafkaProducer(
            bootstrap_servers=f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}"
        )

        # Start the producer
        await producer.start()

        try:
            # Send the message to the player queue topic
            await producer.send_and_wait(Config.PLAYER_QUEUE_TOPIC, message)

            return MatchQueueResult(
                success=True, message="Player added to queue successfully"
            )
        finally:
            # Stop the producer
            await producer.stop()

    except Exception as e:
        logger.error(f"Error adding player to queue: {str(e)}")

        # Fallback to in-memory queue if Kafka is not available
        player_queue.append(entry)
        logger.info(f"Added player {user_id} to in-memory queue (fallback)")

        return MatchQueueResult(
            success=True, message="Player added to in-memory queue (fallback)"
        )


async def send_match_notification(
    user_id: int, match_id: int, opponent_id: int, status: str
):
    """
    Send a match notification to a user via WebSocket.
    """
    message = {
        "in_match": True,
        "match_id": match_id,
        "status": status,
        "opponent_id": opponent_id,
    }
    await manager.send_match_notification(user_id, message)


async def find_match_for_player(
    db: Session, user_id: int, rating: int
) -> Optional[Match]:
    """
    Find a match for a player based on rating similarity.
    This is used by the Kafka consumer to process the queue.
    Players can only have one active or pending match at a time.
    """
    # Check if the player already has an active or pending match
    existing_match = (
        db.query(Match)
        .filter(
            ((Match.player1_id == user_id) | (Match.player2_id == user_id))
            & (
                (Match.status == MatchStatus.PENDING)
                | (Match.status == MatchStatus.ACTIVE)
            )
        )
        .first()
    )

    if existing_match:
        logger.info(
            f"Player {user_id} already has an active or pending match, skipping"
        )
        return None

    # Find users with similar rating in the queue
    rating_range = 100  # Configurable rating range

    # For in-memory queue
    if player_queue:
        # Find potential opponents in the queue
        potential_opponents = [
            entry
            for entry in player_queue
            if entry.user_id != user_id and abs(entry.rating - rating) <= rating_range
        ]

        # Sort by rating similarity
        potential_opponents.sort(key=lambda x: abs(x.rating - rating))

        if potential_opponents:
            # Get the closest rating opponent
            opponent = potential_opponents[0]

            # Check if the opponent already has an active or pending match
            opponent_match = (
                db.query(Match)
                .filter(
                    (
                        (Match.player1_id == opponent.user_id)
                        | (Match.player2_id == opponent.user_id)
                    )
                    & (
                        (Match.status == MatchStatus.PENDING)
                        | (Match.status == MatchStatus.ACTIVE)
                    )
                )
                .first()
            )

            if opponent_match:
                logger.info(
                    f"Opponent {opponent.user_id} already has an active or pending match, skipping"
                )
                # Remove the opponent from the queue to avoid repeatedly trying to match them
                player_queue.remove(opponent)
                return None

            # Remove the opponent from the queue
            player_queue.remove(opponent)

            # Create new match
            new_match = Match(
                player1_id=user_id,
                player2_id=opponent.user_id,
                status=MatchStatus.PENDING,
                start_time=datetime.utcnow(),
            )

            db.add(new_match)
            db.commit()
            db.refresh(new_match)

            # Send match notifications to both players
            await send_match_notification(
                user_id, new_match.id, opponent.user_id, new_match.status
            )
            await send_match_notification(
                opponent.user_id, new_match.id, user_id, new_match.status
            )

            return new_match

    return None


async def check_match_timeouts(db: Session):
    """
    Check for pending matches that have timed out and automatically decline them.
    """
    now = datetime.utcnow()
    timeout_threshold = now - timedelta(seconds=MATCH_ACCEPTANCE_TIMEOUT)

    # Find all pending matches that have timed out
    timed_out_matches = (
        db.query(Match)
        .filter(
            (Match.status == MatchStatus.PENDING)
            & (Match.start_time < timeout_threshold)
        )
        .all()
    )

    # Automatically decline timed out matches
    for match in timed_out_matches:
        match.status = MatchStatus.DECLINED
        match.end_time = now
        logger.info(f"Match {match.id} automatically declined due to timeout")

    if timed_out_matches:
        db.commit()

    return len(timed_out_matches)


async def process_match_queue(db: Session):
    """
    Process the match queue to match players with similar ratings.
    This should be run as a background task or service.
    """
    # Check for timed out matches
    timed_out_count = await check_match_timeouts(db)
    if timed_out_count > 0:
        logger.info(f"Automatically declined {timed_out_count} timed out matches")

    # Create Kafka topics if they don't exist
    # This is done here instead of at container startup
    create_kafka_topics()

    try:
        # Create a Kafka consumer
        consumer = AIOKafkaConsumer(
            Config.PLAYER_QUEUE_TOPIC,
            bootstrap_servers=f"{Config.KAFKA_HOST}:{Config.KAFKA_PORT}",
            group_id="match_processor",
            auto_offset_reset="earliest",
        )

        # Start the consumer
        await consumer.start()

        try:
            # Process messages from the queue
            async for message in consumer:
                try:
                    # Deserialize the message
                    data = json.loads(message.value.decode("utf-8"))
                    entry = PlayerQueueEntry(**data)

                    logger.info(f"Processing player {entry.user_id} from queue")

                    # Find a match for the player
                    match = await find_match_for_player(db, entry.user_id, entry.rating)

                    if match:
                        logger.info(
                            f"Created match {match.id} between players {match.player1_id} and {match.player2_id}"
                        )
                    else:
                        # If no match found, add to in-memory queue for now
                        # In a real implementation, we might want to keep it in Kafka
                        player_queue.append(entry)
                        logger.info(
                            f"No match found for player {entry.user_id}, added to in-memory queue"
                        )

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")

        finally:
            # Stop the consumer
            await consumer.stop()

    except Exception as e:
        logger.error(f"Error starting Kafka consumer: {str(e)}")

        # Process in-memory queue as fallback
        logger.info("Processing in-memory queue as fallback")

        # Group players by rating similarity
        processed_ids = set()
        for entry in sorted(player_queue, key=lambda x: x.timestamp):
            if entry.user_id in processed_ids:
                continue

            match = await find_match_for_player(db, entry.user_id, entry.rating)
            if match:
                processed_ids.add(entry.user_id)
                processed_ids.add(match.player2_id)
                logger.info(
                    f"Created match {match.id} between players {match.player1_id} and {match.player2_id}"
                )
