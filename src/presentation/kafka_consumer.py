import json
import logging
import os
from aiokafka import AIOKafkaConsumer
from src.presentation.websocket import manager

logger = logging.getLogger("kafka_consumer")

KAFKA_BOOTSTRAP_SERVERS = (
    os.getenv("KAFKA_HOST", "kafka") + ":" + os.getenv("KAFKA_PORT", "9092")
)
MATCH_EVENTS_TOPIC = os.getenv("MATCH_EVENTS_TOPIC", "match_events")


async def kafka_ws_consumer():
    consumer = AIOKafkaConsumer(
        MATCH_EVENTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="websocket_notifier",
    )
    await consumer.start()
    logger.info(f"Kafka WebSocket consumer started on topic {MATCH_EVENTS_TOPIC}")
    try:
        async for msg in consumer:
            event = msg.value
            user_id = event.get("user_id")
            payload = event.get("payload")
            if user_id and payload:
                logger.info(f"Forwarding Kafka event to WebSocket for user {user_id}")
                await manager.send_match_notification(user_id, payload)
            else:
                logger.warning(f"Invalid event from Kafka: {event}")
    finally:
        await consumer.stop()
