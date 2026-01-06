"""Performance Agent for bottleneck analysis.

This agent provides read-only access to performance metrics
and helps identify performance issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.config.tool_mappings import PERFORMANCE_TOOLS
from scale_agents.tools.response_formatter import format_health_response

if TYPE_CHECKING:
    from a2a.types import Message
    from agentstack_sdk.a2a.types import AgentMessage
    from agentstack_sdk.server import Server
    from agentstack_sdk.server.context import RunContext


class PerformanceAgent(BaseScaleAgent):
    """Agent for performance analysis and bottleneck detection.

    Capabilities:
    - Analyze filesystem health and performance
    - Monitor node health and status
    - Check storage pool performance
    - Review fileset usage patterns

    This is a read-only agent focused on performance diagnostics.
    """

    def __init__(self) -> None:
        super().__init__(
            name="performance",
            description=(
                "Analyzes performance metrics and identifies bottlenecks. "
                "Provides diagnostics for performance engineers and SREs."
            ),
            allowed_tools=PERFORMANCE_TOOLS,
            read_only=True,
        )

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process a performance analysis request.

        Args:
            message: The incoming message.
            context_id: Optional conversation context ID.

        Returns:
            Formatted performance analysis.
        """
        try:
            user_text = self.get_user_text(message)
            user_lower = user_text.lower()

            # Detect analysis type
            is_node = any(kw in user_lower for kw in ["node", "nodes"])
            is_filesystem = any(kw in user_lower for kw in ["filesystem", "fs"])
            is_pool = any(kw in user_lower for kw in ["pool", "pools", "storage pool"])
            is_usage = any(kw in user_lower for kw in ["usage", "capacity", "space"])
            is_bottleneck = any(kw in user_lower for kw in [
                "bottleneck", "slow", "latency", "throughput", "iops",
                "performance", "issue", "problem",
            ])

            # Route to appropriate analysis
            if is_bottleneck and is_node:
                return await self._analyze_node_performance(user_text, context_id)

            if is_bottleneck and is_filesystem:
                return await self._analyze_filesystem_performance(user_text, context_id)

            if is_pool:
                return await self._analyze_storage_pools(user_text, context_id)

            if is_usage:
                return await self._analyze_usage(user_text, context_id)

            if is_node:
                return await self._get_node_performance(user_text, context_id)

            if is_filesystem:
                return await self._get_filesystem_performance(user_text, context_id)

            # Default: comprehensive performance overview
            return await self._get_performance_overview(context_id)

        except Exception as e:
            return await self.handle_error(e, "performance analysis")

    async def _get_performance_overview(self, context_id: str | None) -> str:
        """Get a comprehensive performance overview."""
        lines = ["**Performance Overview**", ""]

        # Node health and status
        try:
            node_status = await self.call_tool(
                "get_nodes_status",
                {},
                context_id,
            )
            lines.append("**Node Status:**")
            lines.append(format_health_response(node_status, ""))
            lines.append("")
        except Exception as e:
            lines.append(f"**Node Status:** Unable to retrieve ({e})")
            lines.append("")

        # Node health states
        try:
            node_health = await self.call_tool(
                "get_node_health_states",
                {"name": ":all:"},
                context_id,
            )
            lines.append("**Node Health States:**")
            lines.append(format_health_response(node_health, ""))
            lines.append("")
        except Exception as e:
            lines.append(f"**Node Health States:** Unable to retrieve ({e})")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append("*For detailed analysis, specify a component:*")
        lines.append("• 'Analyze node performance for node1'")
        lines.append("• 'Check filesystem gpfs01 performance'")
        lines.append("• 'Show storage pool usage in gpfs01'")

        return "\n".join(lines)

    async def _get_node_performance(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get node performance metrics."""
        node = self.extract_node(text)
        node_spec = node if node else ":all:"

        # Get node status
        status_result = await self.call_tool(
            "get_nodes_status",
            {},
            context_id,
        )

        # Get node health
        health_result = await self.call_tool(
            "get_node_health_states",
            {"name": node_spec},
            context_id,
        )

        lines = []
        title = f"Node Performance: {node}" if node else "Node Performance: All Nodes"
        lines.append(f"**{title}**")
        lines.append("")
        lines.append("**Status:**")
        lines.append(self.format_response(status_result, ""))
        lines.append("")
        lines.append("**Health States:**")
        lines.append(format_health_response(health_result, ""))

        return "\n".join(lines)

    async def _analyze_node_performance(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Analyze node performance for bottlenecks."""
        node = self.extract_node(text)
        node_spec = node if node else ":all:"

        # Gather data
        await self.call_tool(
            "get_nodes_status",
            {},
            context_id,
        )
        health = await self.call_tool(
            "get_node_health_states",
            {"name": node_spec},
            context_id,
        )
        events = await self.call_tool(
            "get_node_health_events",
            {"name": node_spec},
            context_id,
        )

        lines = []
        title = f"Node Performance Analysis: {node}" if node else "Node Performance Analysis"
        lines.append(f"**{title}**")
        lines.append("")

        # Analyze health states for issues
        lines.append("**Health Analysis:**")
        lines.append(format_health_response(health, ""))
        lines.append("")

        # Recent events
        lines.append("**Recent Events:**")
        lines.append(format_health_response(events, ""))
        lines.append("")

        # Analysis summary
        lines.append("**Summary:**")
        lines.append(self._generate_node_summary(health, events))

        return "\n".join(lines)

    async def _get_filesystem_performance(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get filesystem performance metrics."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            # List filesystems
            fs_list = await self.call_tool(
                "list_filesystems",
                {},
                context_id,
            )
            return self.format_response(
                fs_list,
                "Available Filesystems (specify one for performance details)",
            )

        # Get filesystem details
        fs_details = await self.call_tool(
            "get_filesystem",
            {"filesystem": filesystem},
            context_id,
        )

        # Get filesystem health
        fs_health = await self.call_tool(
            "get_filesystem_health_states",
            {"filesystem": filesystem},
            context_id,
        )

        lines = [f"**Filesystem Performance: {filesystem}**", ""]
        lines.append("**Details:**")
        lines.append(self.format_response(fs_details, ""))
        lines.append("")
        lines.append("**Health States:**")
        lines.append(format_health_response(fs_health, ""))

        return "\n".join(lines)

    async def _analyze_filesystem_performance(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Analyze filesystem performance for bottlenecks."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify a filesystem for performance analysis. "
                "Example: 'Analyze performance bottlenecks in filesystem gpfs01'"
            )

        # Gather comprehensive data
        fs_details = await self.call_tool(
            "get_filesystem",
            {"filesystem": filesystem},
            context_id,
        )
        fs_health = await self.call_tool(
            "get_filesystem_health_states",
            {"filesystem": filesystem},
            context_id,
        )
        pools = await self.call_tool(
            "list_storage_pools",
            {"filesystem": filesystem},
            context_id,
        )

        lines = [f"**Filesystem Performance Analysis: {filesystem}**", ""]

        # Health analysis
        lines.append("**Health Status:**")
        lines.append(format_health_response(fs_health, ""))
        lines.append("")

        # Storage pools
        lines.append("**Storage Pools:**")
        lines.append(self.format_response(pools, ""))
        lines.append("")

        # Summary
        lines.append("**Analysis Summary:**")
        lines.append(self._generate_fs_summary(fs_details, fs_health, pools))

        return "\n".join(lines)

    async def _analyze_storage_pools(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Analyze storage pool performance."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify a filesystem. "
                "Example: 'Analyze storage pool performance in filesystem gpfs01'"
            )

        pools = await self.call_tool(
            "list_storage_pools",
            {"filesystem": filesystem},
            context_id,
        )

        lines = [f"**Storage Pool Analysis: {filesystem}**", ""]
        lines.append(self.format_response(pools, ""))
        lines.append("")
        lines.append("*For individual pool details, specify the pool name.*")

        return "\n".join(lines)

    async def _analyze_usage(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Analyze usage patterns."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if fileset and filesystem:
            usage = await self.call_tool(
                "get_fileset_usage",
                {"filesystem": filesystem, "fileset_name": fileset},
                context_id,
            )
            return self.format_response(usage, f"Usage Analysis: {fileset}")

        if filesystem:
            pools = await self.call_tool(
                "list_storage_pools",
                {"filesystem": filesystem},
                context_id,
            )
            return self.format_response(
                pools, f"Storage Utilization: {filesystem}"
            )

        return (
            "Please specify a filesystem or fileset. "
            "Example: 'Analyze usage for fileset user-homes in gpfs01'"
        )

    def _generate_node_summary(self, health: dict, events: dict) -> str:
        """Generate a summary of node health analysis."""
        issues = []

        # Check for critical states
        health_content = self._extract_list_content(health)
        for state in health_content:
            if isinstance(state, dict):
                status = state.get("status", "").upper()
                if status in ("CRITICAL", "ERROR", "UNHEALTHY"):
                    entity = state.get("entityName", "Unknown")
                    reason = state.get("reason", state.get("message", "No details"))
                    issues.append(f"• **{entity}**: {reason}")

        if issues:
            return "**Detected Issues:**\n" + "\n".join(issues)
        return "✅ No performance issues detected."

    def _generate_fs_summary(
        self, details: dict, health: dict, pools: dict
    ) -> str:
        """Generate a summary of filesystem performance analysis."""
        issues = []

        # Check health
        health_content = self._extract_list_content(health)
        for state in health_content:
            if isinstance(state, dict):
                status = state.get("status", "").upper()
                if status in ("CRITICAL", "ERROR", "WARNING"):
                    issues.append(f"• Health issue: {state.get('message', 'Unknown')}")

        if issues:
            return "**Potential Bottlenecks:**\n" + "\n".join(issues)
        return "✅ No obvious bottlenecks detected."

    def _extract_list_content(self, data: dict) -> list:
        """Extract list content from MCP response."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["states", "events", "content", "data"]:
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return val
        return []


def register_performance_agent(server: Server) -> None:
    """Register the Performance Agent with an AgentStack server.

    Args:
        server: The AgentStack server instance.
    """
    agent = PerformanceAgent()

    @server.register(
        name="performance_agent",
        description=agent.description,
    )
    async def performance_handler(context: RunContext, request: AgentMessage) -> str:
        """Handle performance analysis requests."""
        message = request.message
        context_id = getattr(context, "context_id", None)
        return await agent.process(message, context_id)
