from datetime import datetime, timezone
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/ws",
    tags=["WebSocket"],
)


@router.websocket("/transactions")
async def websocket_transactions_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming real-time transaction events,
    ML risk predictions, and automated fraud alerts to connected clients.
    """
    await ws_manager.connect(websocket)

    # Send handshake acknowledgment
    try:
        await ws_manager.send_personal_message(
            {
                "type": "CONNECTION_ESTABLISHED",
                "message": "Connected to BankGuard real-time transaction feed.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            websocket,
        )

        while True:
            # Keep connection open and respond to client heartbeats
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type", "").upper()

                if msg_type == "PING":
                    await ws_manager.send_personal_message(
                        {
                            "type": "PONG",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        websocket,
                    )
            except json.JSONDecodeError:
                # Ignore non-JSON client messages
                pass

    except WebSocketDisconnect:
        logger.info("Client cleanly disconnected from /api/v1/ws/transactions")
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket connection encountered an error: %s", exc)
        await ws_manager.disconnect(websocket)


@router.get("/status")
def get_websocket_status():
    """Diagnostic endpoint to inspect active WebSocket client connections."""
    return {
        "status": "online",
        "active_connections": ws_manager.connection_count,
    }
