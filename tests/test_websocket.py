import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.websocket import router as websocket_router
from backend.app.services.websocket_manager import ConnectionManager


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(websocket_router)
    return TestClient(app)


def test_websocket_status_endpoint(client):
    """Diagnostic endpoint returns active connection status."""
    response = client.get("/api/v1/ws/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "active_connections" in data


def test_connection_manager_broadcast():
    """ConnectionManager broadcasts payload to all connected clients."""
    manager = ConnectionManager()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def accept(self):
            pass

        async def send_text(self, text):
            self.messages.append(json.loads(text))

    c1 = MockWebSocket()
    c2 = MockWebSocket()

    async def scenario():
        await manager.connect(c1)
        await manager.connect(c2)
        assert manager.connection_count == 2

        payload = {"type": "TRANSACTION_PROCESSED", "data": {"id": "TX_999"}}
        delivered = await manager.broadcast(payload)
        assert delivered == 2
        assert len(c1.messages) == 1
        assert len(c2.messages) == 1
        assert c1.messages[0]["type"] == "TRANSACTION_PROCESSED"
        assert c2.messages[0]["data"]["id"] == "TX_999"

        await manager.disconnect(c1)
        assert manager.connection_count == 1

    asyncio.run(scenario())


def test_connection_manager_pruning():
    """Dead connections are pruned cleanly during broadcast."""
    manager = ConnectionManager()

    class MockWebSocket:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail
            self.messages = []

        async def accept(self):
            pass

        async def send_text(self, text):
            if self.should_fail:
                raise RuntimeError("Socket closed abruptly")
            self.messages.append(text)

    good_client = MockWebSocket(should_fail=False)
    bad_client = MockWebSocket(should_fail=True)

    async def scenario():
        await manager.connect(good_client)
        await manager.connect(bad_client)
        assert manager.connection_count == 2

        delivered = await manager.broadcast({"type": "PING"})
        assert delivered == 1
        # Bad client should have been pruned
        assert manager.connection_count == 1
        assert good_client in manager.active_connections
        assert bad_client not in manager.active_connections

    asyncio.run(scenario())
