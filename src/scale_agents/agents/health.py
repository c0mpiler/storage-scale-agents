"""Health Agent for monitoring and diagnostics.

This agent provides read-only access to cluster health information,
node status, and filesystem health events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.config.tool_mappings import HEALTH_TOOLS
from scale_agents.tools.response_formatter import format_health_response

if TYPE_CHECKING:
    from a2a.types import Message


class HealthAgent(BaseScaleAgent):
    """Agent for cluster health monitoring and diagnostics.

    Capabilities:
    - Monitor node health states and events
    - Check filesystem health
    - View cluster status
    - Retrieve node configuration and versions

    This is a read-only agent that cannot modify cluster state.
    """

    def __init__(self) -> None:
        super().__init__(
            name="health",
            description=(
                "Monitors cluster health, node status, and filesystem health events. "
                "Provides diagnostics and alerting information for SREs and NOC operators."
            ),
            allowed_tools=HEALTH_TOOLS,
            read_only=True,
        )

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process a health-related query.

        Args:
            message: The incoming message.
            context_id: Optional conversation context ID.

        Returns:
            Formatted health information.
        """
        try:
            user_text = self.get_user_text(message)
            user_lower = user_text.lower()

            # Route to appropriate handler based on intent
            if any(kw in user_lower for kw in ["node", "nodes"]):
                if "event" in user_lower:
                    return await self._get_node_events(user_text, context_id)
                if any(kw in user_lower for kw in ["config", "configuration"]):
                    return await self._get_node_config(context_id)
                if "version" in user_lower:
                    return await self._get_node_version(user_text, context_id)
                if any(kw in user_lower for kw in ["health", "status", "state"]):
                    return await self._get_node_health(user_text, context_id)
                return await self._get_node_status(context_id)

            if any(kw in user_lower for kw in ["filesystem", "fs"]):
                if "event" in user_lower:
                    return await self._get_filesystem_events(user_text, context_id)
                return await self._get_filesystem_health(user_text, context_id)

            if any(kw in user_lower for kw in ["cluster", "clusters"]):
                return await self._get_cluster_info(context_id)

            if any(kw in user_lower for kw in ["health", "status", "overview", "summary"]):
                return await self._get_health_overview(context_id)

            # Default: provide health overview
            return await self._get_health_overview(context_id)

        except Exception as e:
            return await self.handle_error(e, "health check")

    async def _get_node_health(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get health states for nodes."""
        node = self.extract_node(text)
        node_spec = node if node else ":all:"

        result = await self.call_tool(
            "get_node_health_states",
            {"name": node_spec},
            context_id,
        )

        title = f"Health States for Node: {node}" if node else "Health States: All Nodes"
        return format_health_response(result, title)

    async def _get_node_events(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get health events for nodes."""
        node = self.extract_node(text)
        node_spec = node if node else ":all:"

        result = await self.call_tool(
            "get_node_health_events",
            {"name": node_spec},
            context_id,
        )

        title = f"Health Events for Node: {node}" if node else "Health Events: All Nodes"
        return format_health_response(result, title)

    async def _get_node_status(self, context_id: str | None) -> str:
        """Get status of all nodes."""
        result = await self.call_tool(
            "get_nodes_status",
            {},
            context_id,
        )
        return format_health_response(result, "Node Status Overview")

    async def _get_node_config(self, context_id: str | None) -> str:
        """Get configuration of all nodes."""
        result = await self.call_tool(
            "get_nodes_config",
            {},
            context_id,
        )
        return self.format_response(result, "Node Configuration")

    async def _get_node_version(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get version information for a node."""
        node = self.extract_node(text)
        if not node:
            # Get cluster version instead
            result = await self.call_tool(
                "get_version",
                {},
                context_id,
            )
            return self.format_response(result, "Storage Scale Version")

        result = await self.call_tool(
            "get_node_version",
            {"node": node},
            context_id,
        )
        return self.format_response(result, f"Version: Node {node}")

    async def _get_filesystem_health(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get health states for filesystems."""
        filesystem = self.extract_filesystem(text)
        if not filesystem:
            # List all filesystems first to give context
            return (
                "Please specify a filesystem name. "
                "Example: 'Show health for filesystem gpfs01'"
            )

        result = await self.call_tool(
            "get_filesystem_health_states",
            {"filesystem": filesystem},
            context_id,
        )
        return format_health_response(result, f"Filesystem Health: {filesystem}")

    async def _get_filesystem_events(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get health events for filesystems."""
        filesystem = self.extract_filesystem(text)
        if not filesystem:
            return (
                "Please specify a filesystem name. "
                "Example: 'Show events for filesystem gpfs01'"
            )

        result = await self.call_tool(
            "get_filesystem_health_events",
            {"filesystem_name": filesystem},
            context_id,
        )
        return format_health_response(result, f"Filesystem Events: {filesystem}")

    async def _get_cluster_info(self, context_id: str | None) -> str:
        """Get cluster information."""
        result = await self.call_tool(
            "list_clusters",
            {},
            context_id,
        )
        return self.format_response(result, "Cluster Information")

    async def _get_health_overview(self, context_id: str | None) -> str:
        """Get a comprehensive health overview."""
        lines = ["**Cluster Health Overview**", ""]

        # Get node status
        try:
            node_result = await self.call_tool(
                "get_nodes_status",
                {},
                context_id,
            )
            lines.append("**Node Status:**")
            lines.append(format_health_response(node_result, ""))
            lines.append("")
        except Exception as e:
            lines.append(f"**Node Status:** Unable to retrieve ({e})")
            lines.append("")

        # Get node health states
        try:
            health_result = await self.call_tool(
                "get_node_health_states",
                {"name": ":all:"},
                context_id,
            )
            lines.append("**Health States:**")
            lines.append(format_health_response(health_result, ""))
        except Exception as e:
            lines.append(f"**Health States:** Unable to retrieve ({e})")

        return "\n".join(lines)
