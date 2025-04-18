# Match System

This directory contains the implementation of the match system for Algo Rumble. The match system is responsible for matching players with similar ratings and creating matches between them.

## How it works

1. When a user wants to find a match, they call the `/match/find` endpoint with their user ID.
2. The user is added to a queue using Kafka.
3. A consumer service processes the queue and matches players with similar ratings.
4. When two players with similar ratings are found, a match is created between them.
5. Players are notified about the match via WebSocket if they have an active connection.
6. Players can also check their match status using the `/match/queue/status` endpoint (fallback method).
7. Once matched, players have 15 seconds to accept the match using the `/match/accept/{match_id}` endpoint. If not accepted within this time, the match is automatically declined.
8. Players can view their active matches using the `/match/active` endpoint.
9. Players can only have one active or pending match at a time.

## Components

### Models

- `Match`: Represents a match between two players.
- `MatchStatus`: Enum representing the possible states of a match (CREATED, PENDING, ACTIVE, COMPLETED, DECLINED, CANCELLED).

### Schemas

- `MatchBase`: Base schema for match data.
- `MatchCreate`: Schema for creating a new match.
- `MatchResponse`: Schema for returning match data.
- `PlayerQueueEntry`: Schema for representing a player in the match queue.
- `MatchQueueResult`: Schema for representing the result of a match queue operation.

### Services

- `add_player_to_queue`: Adds a player to the match queue using Kafka.
- `find_match_for_player`: Finds a match for a player based on rating similarity.
- `process_match_queue`: Processes the match queue to match players with similar ratings.
- `send_match_notification`: Sends a match notification to a user via WebSocket.

### WebSockets

- `ConnectionManager`: Manages WebSocket connections for real-time match notifications.
- `websocket_endpoint`: WebSocket endpoint for real-time match notifications.

### Consumer

The `consumer.py` file contains a service that runs continuously to process the match queue. It consumes messages from the Kafka queue and matches players with similar ratings.

## Configuration

The match system uses the following configuration properties:

- `KAFKA_HOST`: The hostname of the Kafka broker (default: "kafka").
- `KAFKA_PORT`: The port of the Kafka broker (default: 9092).
- `PLAYER_QUEUE_TOPIC`: The Kafka topic for the player queue (default: "player_queue").
- `MATCH_EVENTS_TOPIC`: The Kafka topic for match events (default: "match_events").

## Deployment

The match system is deployed as part of the main application, with the consumer service running as a separate container. The docker-compose.yml file includes both the main application and the consumer service.
