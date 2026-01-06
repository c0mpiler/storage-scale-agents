"""Tests for the MCP client."""

from unittest.mock import AsyncMock, patch

import pytest

from scale_agents.core.exceptions import MCPConnectionError
from scale_agents.tools.mcp_client import MCPClient


class TestMCPClient:
    """Tests for MCPClient class."""

    @pytest.fixture
    def client(self):
        """Create an MCP client instance."""
        return MCPClient(
            url="http://test-server:8000/mcp",
            timeout=30.0,
            max_retries=3,
        )

    def test_init_default_values(self):
        """Should use default values from settings."""
        client = MCPClient()
        assert client.timeout > 0
        assert client.max_retries >= 0

    def test_init_custom_values(self, client):
        """Should use provided values."""
        assert client.url == "http://test-server:8000/mcp"
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_not_initialized_by_default(self, client):
        """Client should not be initialized until connect is called."""
        assert client._initialized is False
        assert client._session_id is None

    @pytest.mark.asyncio
    async def test_connect_sets_initialized(self, client):
        """Connect should set initialized flag."""
        with (
            patch("httpx.AsyncClient") as mock_async_client,
            patch.object(client, "_initialize_session", new_callable=AsyncMock),
        ):
            mock_async_client.return_value = AsyncMock()
            await client.connect()
            assert client._initialized is True

    @pytest.mark.asyncio
    async def test_disconnect_clears_state(self, client):
        """Disconnect should clear all state."""
        client._initialized = True
        client._session_id = "test-session"
        client._client = AsyncMock()
        client._request_counter = 10

        await client.disconnect()

        assert client._initialized is False
        assert client._session_id is None
        assert client._client is None
        assert client._request_counter == 0

    @pytest.mark.asyncio
    async def test_call_tool_raises_when_not_connected(self, client):
        """Should raise MCPConnectionError when not connected."""
        with pytest.raises(MCPConnectionError):
            await client.call_tool("test_tool", {})

    def test_next_request_id_increments(self, client):
        """Request IDs should increment."""
        id1 = client._next_request_id()
        id2 = client._next_request_id()
        id3 = client._next_request_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3


class TestMCPClientContextManager:
    """Tests for MCPClient async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(self):
        """Context manager should connect on enter and disconnect on exit."""
        with patch.object(MCPClient, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(MCPClient, "disconnect", new_callable=AsyncMock) as mock_disconnect:
                async with MCPClient():
                    mock_connect.assert_called_once()

                mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_error(self):
        """Context manager should disconnect even if an error occurs."""
        with patch.object(MCPClient, "connect", new_callable=AsyncMock):
            with patch.object(MCPClient, "disconnect", new_callable=AsyncMock) as mock_disconnect:
                try:
                    async with MCPClient():
                        raise ValueError("Test error")
                except ValueError:
                    pass

                mock_disconnect.assert_called_once()
