import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections for real-time telemetry broadcast.
    Provides async-safe connection registration and broadcast with dead-connection pruning.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and add it to the active pool."""
        await websocket.accept()
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Active connections: %d",
            len(self.active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected. Active connections: %d",
            len(self.active_connections),
        )

    async def send_personal_message(
        self,
        message: dict[str, Any],
        websocket: WebSocket,
    ) -> None:
        """Send a JSON message to a specific connected client."""
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict[str, Any]) -> int:
        """
        Broadcast a JSON message to all active WebSocket clients.
        Automatically removes dead/broken connections.
        Returns the count of successfully notified clients.
        """
        if not self.active_connections:
            return 0

        payload = json.dumps(message)
        dead_connections: list[WebSocket] = []
        delivered = 0

        # Snapshot of connections to allow safe iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
                delivered += 1
            except Exception as exc:
                logger.warning(
                    "Failed to deliver message to WebSocket client: %s. Marking for removal.",
                    exc,
                )
                dead_connections.append(connection)

        if dead_connections:
            for dead in dead_connections:
                if dead in self.active_connections:
                    self.active_connections.remove(dead)
            logger.info(
                "Pruned %d dead WebSocket connections. Remaining: %d",
                len(dead_connections),
                len(self.active_connections),
            )

        return delivered

    @property
    def connection_count(self) -> int:
        """Return the number of currently active connections."""
        return len(self.active_connections)


# Global singleton instance for application-wide broadcast access
ws_manager = ConnectionManager()
