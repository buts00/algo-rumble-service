import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time match notifications.
    """

    def __init__(self):
        # Maps user_id to a list of active WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """
        Connect a WebSocket for a specific user.
        """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(
            f"User {user_id} connected to WebSocket. Total connections: {len(self.active_connections[user_id])}"
        )

    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Disconnect a WebSocket for a specific user.
        """
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_match_notification(self, user_id: int, message: dict):
        """
        Send a match notification to a specific user.
        """
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                    logger.info(f"Match notification sent to user {user_id}")
                except Exception as e:
                    logger.error(
                        f"Error sending match notification to user {user_id}: {str(e)}"
                    )
        else:
            logger.info(f"No active WebSocket connections for user {user_id}")


# Create a global connection manager instance
manager = ConnectionManager()
