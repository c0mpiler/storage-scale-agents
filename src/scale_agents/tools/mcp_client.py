"""MCP Client for communicating with scale-mcp-server.

This module provides a robust async client for the Model Context Protocol,
handling session management, retries, and error handling.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import orjson
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scale_agents.config.settings import settings
from scale_agents.core.exceptions import MCPConnectionError, MCPToolError
from scale_agents.core.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """Async client for MCP server communication.

    Handles session initialization, tool calls, and proper cleanup.
    Implements retry logic for transient failures.
    """

    def __init__(
        self,
        url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the MCP client.

        Args:
            url: MCP server URL. Defaults to settings.mcp_server_url.
            timeout: Request timeout in seconds. Defaults to settings.mcp_timeout.
            max_retries: Max retry attempts. Defaults to settings.mcp_max_retries.
        """
        self.url = url or settings.mcp_server_url
        self.timeout = timeout or settings.mcp_timeout
        self.max_retries = max_retries or settings.mcp_max_retries

        self._session_id: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._request_counter: int = 0
        self._initialized: bool = False

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Establish connection and initialize MCP session."""
        if self._initialized:
            return

        logger.debug("connecting_to_mcp", url=self.url)

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            http2=True,
        )

        try:
            await self._initialize_session()
            self._initialized = True
            logger.info("mcp_session_established", session_id=self._session_id)
        except Exception as e:
            await self.disconnect()
            raise MCPConnectionError(
                message="Failed to initialize MCP session",
                url=self.url,
                cause=e,
            ) from e

    async def disconnect(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._session_id = None
        self._initialized = False
        self._request_counter = 0
        logger.debug("mcp_client_disconnected")

    def _next_request_id(self) -> int:
        """Generate the next request ID."""
        self._request_counter += 1
        return self._request_counter

    async def _initialize_session(self) -> None:
        """Initialize the MCP session with the server."""
        if self._client is None:
            raise MCPConnectionError("Client not initialized")

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "scale-agents",
                    "version": "1.0.0",
                },
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with self._client.stream(
            "POST", self.url, headers=headers, json=payload
        ) as response:
            # Extract session ID from headers
            self._session_id = response.headers.get(
                "Mcp-Session-Id"
            ) or response.headers.get("mcp-session-id")

            if not self._session_id:
                raise MCPConnectionError("Server did not provide session ID")

            # Process SSE stream for initialization result
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        msg = orjson.loads(line[6:])
                        if "result" in msg:
                            logger.debug("mcp_initialized", result=msg["result"])
                            return
                        if "error" in msg:
                            raise MCPConnectionError(
                                f"Initialization error: {msg['error']}"
                            )
                    except orjson.JSONDecodeError:
                        continue

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool's result data.

        Raises:
            MCPConnectionError: If not connected to MCP server.
            MCPToolError: If the tool call fails.
        """
        if not self._initialized or self._client is None or not self._session_id:
            raise MCPConnectionError("MCP client not connected")

        arguments = arguments or {}

        logger.debug(
            "calling_mcp_tool",
            tool_name=tool_name,
            arguments=arguments,
        )

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self._session_id,
        }

        result = None

        try:
            async with self._client.stream(
                "POST", self.url, headers=headers, json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            msg = orjson.loads(line[6:])
                            if "result" in msg:
                                result = msg["result"]
                                break
                            if "error" in msg:
                                raise MCPToolError(
                                    message=f"Tool error: {msg['error']}",
                                    tool_name=tool_name,
                                    arguments=arguments,
                                    error_code=msg["error"].get("code"),
                                )
                        except orjson.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            raise MCPToolError(
                message=f"HTTP error during tool call: {e}",
                tool_name=tool_name,
                arguments=arguments,
                cause=e,
            ) from e

        if result is None:
            raise MCPToolError(
                message="No result received from MCP server",
                tool_name=tool_name,
                arguments=arguments,
            )

        logger.debug(
            "mcp_tool_result",
            tool_name=tool_name,
            has_content="content" in result if isinstance(result, dict) else False,
        )

        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools from the MCP server.

        Returns:
            List of tool definitions.
        """
        if not self._initialized or self._client is None or not self._session_id:
            raise MCPConnectionError("MCP client not connected")

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {},
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self._session_id,
        }

        async with self._client.stream(
            "POST", self.url, headers=headers, json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        msg = orjson.loads(line[6:])
                        if "result" in msg:
                            return msg["result"].get("tools", [])
                        if "error" in msg:
                            raise MCPToolError(
                                message=f"Failed to list tools: {msg['error']}",
                                tool_name="tools/list",
                            )
                    except orjson.JSONDecodeError:
                        continue

        return []


# Global client instance for simple usage
_global_client: MCPClient | None = None
_global_lock = asyncio.Lock()


@asynccontextmanager
async def get_client() -> AsyncIterator[MCPClient]:
    """Get a connected MCP client instance.

    Uses a global client with connection pooling for efficiency.

    Yields:
        Connected MCPClient instance.
    """
    global _global_client

    async with _global_lock:
        if _global_client is None:
            _global_client = MCPClient()
            await _global_client.connect()

    try:
        yield _global_client
    except MCPConnectionError:
        # Reset global client on connection errors
        async with _global_lock:
            if _global_client:
                await _global_client.disconnect()
                _global_client = None
        raise


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    """Convenience function to call an MCP tool.

    Creates a new client connection for each call.
    For better performance in high-throughput scenarios,
    use the MCPClient class directly with connection reuse.

    Args:
        tool_name: Name of the tool to call.
        arguments: Arguments to pass to the tool.

    Returns:
        The tool's result data.
    """
    async with MCPClient() as client:
        return await client.call_tool(tool_name, arguments)
