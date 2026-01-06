"""Quota Agent for capacity management.

This agent handles quota management and capacity monitoring,
including setting quotas and checking usage.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.config.tool_mappings import QUOTA_TOOLS

if TYPE_CHECKING:
    from a2a.types import Message
    from agentstack_sdk.a2a.types import AgentMessage
    from agentstack_sdk.server import Server
    from agentstack_sdk.server.context import RunContext


class QuotaAgent(BaseScaleAgent):
    """Agent for quota and capacity management.

    Capabilities:
    - List quotas for filesystems
    - Set and update quotas
    - Delete quotas
    - Monitor fileset usage

    Destructive operations require user confirmation.
    """

    def __init__(self) -> None:
        super().__init__(
            name="quota",
            description=(
                "Manages quotas and monitors capacity usage. "
                "Handles quota operations for storage administrators and project leads."
            ),
            allowed_tools=QUOTA_TOOLS,
            read_only=False,
        )

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process a quota management request.

        Args:
            message: The incoming message.
            context_id: Optional conversation context ID.

        Returns:
            Formatted response.
        """
        try:
            user_text = self.get_user_text(message)
            user_lower = user_text.lower()

            # Detect operation type
            is_set = any(kw in user_lower for kw in ["set", "create", "add", "update", "change"])
            is_delete = any(kw in user_lower for kw in ["delete", "remove", "clear"])
            is_list = any(kw in user_lower for kw in ["list", "show", "get", "all"])
            is_usage = any(kw in user_lower for kw in ["usage", "used", "capacity", "size"])

            # Route to appropriate handler
            if is_usage:
                return await self._get_usage(user_text, context_id)

            if is_set:
                return await self._set_quota(user_text, context_id)

            if is_delete:
                return await self._delete_quota(user_text, context_id)

            if is_list or "quota" in user_lower:
                return await self._list_quotas(user_text, context_id)

            # Default: list quotas
            return await self._list_quotas(user_text, context_id)

        except Exception as e:
            return await self.handle_error(e, "quota operation")

    async def _list_quotas(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """List quotas for a filesystem."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'List quotas in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "list_quotas",
            {"filesystem": filesystem},
            context_id,
        )
        return self.format_response(result, f"Quotas: {filesystem}")

    async def _get_usage(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get usage information for a fileset."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem or not fileset:
            return (
                "Please specify both filesystem and fileset names. "
                "Example: 'Show usage for fileset user-homes in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "get_fileset_usage",
            {"filesystem": filesystem, "fileset_name": fileset},
            context_id,
        )
        return self._format_usage_response(result, fileset)

    async def _set_quota(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Set or update a quota."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Set 10TB quota on fileset user-homes in filesystem gpfs01'"
            )

        # Extract quota value
        quota_value = self._extract_quota_value(text)
        if not quota_value:
            return (
                "Please specify the quota value. "
                "Example: 'Set 10TB quota on fileset user-homes'"
            )

        # Build quota data
        quota_data: dict = {
            "blockHardLimit": quota_value,
            "blockSoftLimit": int(quota_value * 0.9),  # 90% for soft limit
        }

        if fileset:
            quota_data["objectName"] = fileset
            quota_data["quotaType"] = "FILESET"
        else:
            return (
                "Please specify the fileset name. "
                "Example: 'Set 10TB quota on fileset user-homes in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "set_quota",
            {"filesystem": filesystem, "quota_data": quota_data},
            context_id,
        )

        # Format readable quota value
        readable_quota = self._format_bytes(quota_value)
        return self.format_response(
            result, f"Quota Set: {fileset} = {readable_quota}"
        )

    async def _delete_quota(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Delete a quota."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Delete quota for fileset user-homes in filesystem gpfs01'"
            )

        quota_data: dict = {}
        if fileset:
            quota_data["objectName"] = fileset
            quota_data["quotaType"] = "FILESET"
        else:
            return (
                "Please specify the fileset name. "
                "Example: 'Delete quota for fileset user-homes'"
            )

        result = await self.call_tool(
            "delete_quota",
            {"filesystem": filesystem, "quota_data": quota_data},
            context_id,
        )
        return self.format_response(result, f"Quota Deleted: {fileset}")

    def _extract_quota_value(self, text: str) -> int | None:
        """Extract quota value in bytes from text.

        Supports formats like: 10TB, 500GB, 1024MB, 10 TB, etc.
        """
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(tb|terabyte|terabytes)",
            r"(\d+(?:\.\d+)?)\s*(gb|gigabyte|gigabytes)",
            r"(\d+(?:\.\d+)?)\s*(mb|megabyte|megabytes)",
            r"(\d+(?:\.\d+)?)\s*(kb|kilobyte|kilobytes)",
            r"(\d+(?:\.\d+)?)\s*(pb|petabyte|petabytes)",
        ]

        multipliers = {
            "pb": 1024**5,
            "petabyte": 1024**5,
            "petabytes": 1024**5,
            "tb": 1024**4,
            "terabyte": 1024**4,
            "terabytes": 1024**4,
            "gb": 1024**3,
            "gigabyte": 1024**3,
            "gigabytes": 1024**3,
            "mb": 1024**2,
            "megabyte": 1024**2,
            "megabytes": 1024**2,
            "kb": 1024,
            "kilobyte": 1024,
            "kilobytes": 1024,
        }

        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()
                return int(value * multipliers.get(unit, 1))

        return None

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string."""
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        value = float(bytes_value)
        unit_index = 0

        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        if value == int(value):
            return f"{int(value)} {units[unit_index]}"
        return f"{value:.2f} {units[unit_index]}"

    def _format_usage_response(self, result: dict, fileset: str) -> str:
        """Format usage response with visual indicators."""
        lines = [f"**Usage: {fileset}**", ""]

        # Try to extract usage data
        content = result
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and content:
                content = content[0]
                if isinstance(content, dict) and "text" in content:
                    import orjson
                    with contextlib.suppress(Exception):
                        content = orjson.loads(content["text"])

        if isinstance(content, dict):
            used = content.get("blockUsage", content.get("used", 0))
            limit = content.get("blockHardLimit", content.get("limit", 0))

            if limit > 0:
                percentage = (used / limit) * 100
                used_str = self._format_bytes(used)
                limit_str = self._format_bytes(limit)

                # Visual progress bar
                filled = int(percentage / 5)  # 20 char bar
                bar = "█" * filled + "░" * (20 - filled)

                status_emoji = "🟢" if percentage < 80 else "🟡" if percentage < 95 else "🔴"

                lines.append(f"**Used:** {used_str} / {limit_str}")
                lines.append(f"**Percentage:** {percentage:.1f}% {status_emoji}")
                lines.append(f"```[{bar}]```")
            else:
                lines.append(self.format_response(content, ""))
        else:
            lines.append(str(content))

        return "\n".join(lines)


def register_quota_agent(server: Server) -> None:
    """Register the Quota Agent with an AgentStack server.

    Args:
        server: The AgentStack server instance.
    """
    agent = QuotaAgent()

    @server.register(
        name="quota_agent",
        description=agent.description,
    )
    async def quota_handler(context: RunContext, request: AgentMessage) -> str:
        """Handle quota management requests."""
        message = request.message
        context_id = getattr(context, "context_id", None)
        return await agent.process(message, context_id)
