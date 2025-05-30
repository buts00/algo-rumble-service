import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manager for WebSocket connections.
    Handles connecting, disconnecting, and sending messages to connected clients.
    """

    def __init__(self):
        # Map of user_id to list of connected WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Connect a WebSocket for a user.
        A user can have multiple active connections (e.g., multiple browser tabs).
        """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(
            f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections[user_id])}"
        )

    def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Disconnect a WebSocket for a user.
        """
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                logger.info(
                    f"WebSocket disconnected for user {user_id}. Remaining connections: {len(self.active_connections[user_id])}"
                )

            # Clean up if no more connections for this user
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                logger.info(
                    f"No more connections for user {user_id}. Removed from active connections."
                )

    async def send_match_notification(self, user_id: str, message: Any):
        """
        Send a notification to all WebSocket connections for a user.
        """
        if user_id in self.active_connections:
            disconnected_websockets = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                    logger.debug(f"Notification sent to user {user_id}")
                except Exception as e:
                    logger.error(
                        f"Error sending notification to user {user_id}: {str(e)}"
                    )
                    disconnected_websockets.append(websocket)

            # Clean up any disconnected websockets
            for websocket in disconnected_websockets:
                self.disconnect(websocket, user_id)
        else:
            logger.debug(f"No active WebSocket connections for user {user_id}")


# Create a singleton instance
manager = WebSocketManager()
