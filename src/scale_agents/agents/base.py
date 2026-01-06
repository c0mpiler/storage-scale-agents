"""Base agent class for Scale Agents.

Provides common functionality for all specialized agents.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from a2a.utils.message import get_message_text

from scale_agents.config.tool_mappings import DESTRUCTIVE_TOOLS
from scale_agents.core.exceptions import (
    ConfirmationRequiredError,
    MCPToolError,
    ToolNotAllowedError,
)
from scale_agents.core.logging import get_logger
from scale_agents.tools.confirmable import check_confirmation, requires_confirmation
from scale_agents.tools.mcp_client import MCPClient
from scale_agents.tools.response_formatter import format_error_response, format_response

if TYPE_CHECKING:
    from a2a.types import Message


class BaseScaleAgent(ABC):
    """Base class for all Scale agents.

    Provides common functionality including:
    - Tool whitelist enforcement
    - Confirmation handling for destructive operations
    - MCP client management
    - Response formatting
    - Parameter extraction utilities
    """

    def __init__(
        self,
        name: str,
        description: str,
        allowed_tools: frozenset[str],
        read_only: bool = True,
    ) -> None:
        """Initialize the agent.

        Args:
            name: Agent name for identification.
            description: Human-readable description of the agent's purpose.
            allowed_tools: Set of MCP tool names this agent can use.
            read_only: If True, agent cannot use destructive tools.
        """
        self.name = name
        self.description = description
        self.allowed_tools = allowed_tools
        self.read_only = read_only
        self.logger = get_logger(f"agent.{name}")

    @abstractmethod
    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process an incoming message and return a response.

        Args:
            message: The incoming A2A message.
            context_id: Optional conversation context ID.

        Returns:
            The agent's response as a string.
        """
        pass

    def get_user_text(self, message: Message) -> str:
        """Extract text content from an A2A message.

        Args:
            message: The A2A message.

        Returns:
            The text content of the message.
        """
        return get_message_text(message)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        context_id: str | None = None,
        force_confirm: bool = False,
    ) -> Any:
        """Call an MCP tool with whitelist and confirmation checks.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments for the tool.
            context_id: Optional context ID for confirmation tracking.
            force_confirm: If True, skip confirmation requirements.

        Returns:
            The tool's result.

        Raises:
            ToolNotAllowedError: If tool is not in agent's whitelist.
            ConfirmationRequiredError: If confirmation is needed.
            MCPToolError: If the tool call fails.
        """
        arguments = arguments or {}

        # Enforce whitelist
        if tool_name not in self.allowed_tools:
            self.logger.warning(
                "tool_not_allowed",
                tool_name=tool_name,
                agent=self.name,
            )
            raise ToolNotAllowedError(
                tool_name=tool_name,
                agent_name=self.name,
                allowed_tools=self.allowed_tools,
            )

        # Check for read-only enforcement
        if self.read_only and tool_name in DESTRUCTIVE_TOOLS:
            raise ToolNotAllowedError(
                tool_name=tool_name,
                agent_name=self.name,
                allowed_tools=self.allowed_tools,
            )

        # Check confirmation requirements
        if requires_confirmation(tool_name, arguments):
            check_confirmation(
                tool_name=tool_name,
                arguments=arguments,
                context_id=context_id,
                force_confirm=force_confirm,
            )

        # Execute the tool
        self.logger.info(
            "calling_tool",
            tool_name=tool_name,
            arguments=arguments,
        )

        async with MCPClient() as client:
            result = await client.call_tool(tool_name, arguments)

        self.logger.debug(
            "tool_result",
            tool_name=tool_name,
            success=True,
        )

        return result

    def extract_param(
        self,
        text: str,
        param_name: str,
        patterns: list[str] | None = None,
    ) -> str | None:
        """Extract a parameter value from user text.

        Args:
            text: The user's message text.
            param_name: Name of the parameter to extract.
            patterns: Optional list of regex patterns to try.

        Returns:
            The extracted parameter value or None.
        """
        if patterns is None:
            # Default patterns for common parameter extraction
            patterns = [
                rf"{param_name}\s+['\"]?(\S+)['\"]?",
                rf"{param_name}[=:]\s*['\"]?(\S+)['\"]?",
                rf"(?:in|on|for|from)\s+{param_name}\s+['\"]?(\S+)['\"]?",
            ]

        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip("'\"")

        return None

    def extract_filesystem(self, text: str) -> str | None:
        """Extract filesystem name from user text.

        Args:
            text: The user's message text.

        Returns:
            Filesystem name or None.
        """
        patterns = [
            r"filesystem\s+['\"]?(\w+)['\"]?",
            r"fs\s+['\"]?(\w+)['\"]?",
            r"in\s+['\"]?(\w+)['\"]?\s+filesystem",
            r"(?:on|in|for|from)\s+['\"]?(\w+)['\"]?(?:\s|$)",
        ]
        return self.extract_param(text, "filesystem", patterns)

    def extract_fileset(self, text: str) -> str | None:
        """Extract fileset name from user text.

        Args:
            text: The user's message text.

        Returns:
            Fileset name or None.
        """
        patterns = [
            r"fileset\s+['\"]?(\S+)['\"]?",
            r"fileset[=:]\s*['\"]?(\S+)['\"]?",
        ]
        return self.extract_param(text, "fileset", patterns)

    def extract_node(self, text: str) -> str | None:
        """Extract node name from user text.

        Args:
            text: The user's message text.

        Returns:
            Node name or None.
        """
        patterns = [
            r"node\s+['\"]?(\S+)['\"]?",
            r"node[=:]\s*['\"]?(\S+)['\"]?",
            r"(?:on|for)\s+node\s+['\"]?(\S+)['\"]?",
        ]
        return self.extract_param(text, "node", patterns)

    def format_response(self, data: Any, title: str | None = None) -> str:
        """Format tool response data for display.

        Args:
            data: The data to format.
            title: Optional title.

        Returns:
            Formatted response string.
        """
        return format_response(data, title)

    def format_error(self, error: str | Exception, context: str | None = None) -> str:
        """Format an error for display.

        Args:
            error: The error.
            context: Optional context.

        Returns:
            Formatted error string.
        """
        return format_error_response(error, context)

    async def handle_error(
        self,
        error: Exception,
        context: str | None = None,
    ) -> str:
        """Handle an exception and return a user-friendly response.

        Args:
            error: The exception that occurred.
            context: Optional context about what was attempted.

        Returns:
            User-friendly error message.
        """
        self.logger.error(
            "agent_error",
            error=str(error),
            context=context,
            error_type=type(error).__name__,
        )

        if isinstance(error, ConfirmationRequiredError):
            return error.format_confirmation_prompt()

        if isinstance(error, ToolNotAllowedError):
            return (
                f"I'm not authorized to perform that operation.\n\n"
                f"**Reason:** {error.message}"
            )

        if isinstance(error, MCPToolError):
            return self.format_error(
                f"The operation failed: {error.message}",
                context=f"Tool: {error.tool_name}",
            )

        return self.format_error(error, context)
