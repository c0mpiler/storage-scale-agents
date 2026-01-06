"""Admin Agent for cluster administration.

This agent handles high-privilege operations including cluster management,
node lifecycle, and snapshot operations.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.config.tool_mappings import ADMIN_TOOLS

if TYPE_CHECKING:
    from a2a.types import Message
    from agentstack_sdk.a2a.types import AgentMessage
    from agentstack_sdk.server import Server
    from agentstack_sdk.server.context import RunContext


class AdminAgent(BaseScaleAgent):
    """Agent for cluster administration and high-privilege operations.

    Capabilities:
    - Cluster management and configuration
    - Node lifecycle (start, stop, add)
    - Snapshot management
    - NSD management
    - Remote cluster authorization

    All write operations require user confirmation due to high risk.
    """

    def __init__(self) -> None:
        super().__init__(
            name="admin",
            description=(
                "Handles cluster administration, node lifecycle, and snapshot management. "
                "Reserved for cluster administrators with elevated privileges."
            ),
            allowed_tools=ADMIN_TOOLS,
            read_only=False,
        )

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process an administration request.

        Args:
            message: The incoming message.
            context_id: Optional conversation context ID.

        Returns:
            Formatted response.
        """
        try:
            user_text = self.get_user_text(message)
            user_lower = user_text.lower()

            # Detect operation category
            is_snapshot = any(kw in user_lower for kw in ["snapshot", "snapshots"])
            is_node = any(kw in user_lower for kw in ["node", "nodes"]) and not is_snapshot
            is_cluster = any(kw in user_lower for kw in ["cluster", "remote"])
            is_nsd = "nsd" in user_lower
            is_config = any(kw in user_lower for kw in ["config", "configuration", "setting"])

            # Detect operation type
            is_create = any(kw in user_lower for kw in ["create", "add", "new", "make"])
            is_delete = any(kw in user_lower for kw in ["delete", "remove", "destroy"])
            is_list = any(kw in user_lower for kw in ["list", "show", "get", "all"])
            is_start = "start" in user_lower
            is_stop = "stop" in user_lower

            # Route to appropriate handler
            if is_snapshot:
                if is_create:
                    return await self._create_snapshot(user_text, context_id)
                if is_delete:
                    return await self._delete_snapshot(user_text, context_id)
                return await self._list_snapshots(user_text, context_id)

            if is_node:
                if is_start:
                    return await self._start_nodes(user_text, context_id)
                if is_stop:
                    return await self._stop_nodes(user_text, context_id)
                if is_create:
                    return await self._add_node(user_text, context_id)

            if is_cluster:
                if "remote" in user_lower:
                    return await self._handle_remote_cluster(user_text, context_id)
                return await self._get_cluster_info(context_id)

            if is_nsd:
                if is_create:
                    return await self._create_nsd(user_text, context_id)
                if is_delete:
                    return await self._delete_nsd(user_text, context_id)
                if is_list:
                    return await self._list_nsds(context_id)
                return await self._get_nsd(user_text, context_id)

            if is_config:
                return await self._get_config(user_text, context_id)

            # Default: show cluster info
            return await self._get_cluster_info(context_id)

        except Exception as e:
            return await self.handle_error(e, "admin operation")

    async def _get_cluster_info(self, context_id: str | None) -> str:
        """Get cluster information."""
        result = await self.call_tool(
            "list_clusters",
            {},
            context_id,
        )
        return self.format_response(result, "Cluster Information")

    async def _list_snapshots(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """List snapshots."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if fileset and filesystem:
            # Fileset snapshots
            result = await self.call_tool(
                "list_fileset_snapshots",
                {"filesystem": filesystem, "fileset": fileset},
                context_id,
            )
            return self.format_response(
                result, f"Snapshots for Fileset: {fileset}"
            )

        if filesystem:
            # Filesystem snapshots
            result = await self.call_tool(
                "list_snapshots",
                {"filesystem": filesystem},
                context_id,
            )
            return self.format_response(
                result, f"Snapshots for Filesystem: {filesystem}"
            )

        return (
            "Please specify a filesystem. "
            "Example: 'List snapshots in filesystem gpfs01'"
        )

    async def _create_snapshot(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Create a snapshot."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        # Extract snapshot name
        snapshot_match = re.search(
            r"snapshot\s+['\"]?(\S+)['\"]?", text.lower()
        )
        snapshot_name = snapshot_match.group(1) if snapshot_match else None

        if not snapshot_name:
            # Try alternative patterns
            create_match = re.search(
                r"create\s+(?:snapshot\s+)?['\"]?(\S+)['\"]?", text.lower()
            )
            if create_match:
                snapshot_name = create_match.group(1)
                if snapshot_name in ["snapshot", "in", "for", "on"]:
                    snapshot_name = None

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Create snapshot daily-backup in filesystem gpfs01'"
            )

        if not snapshot_name:
            return (
                "Please specify the snapshot name. "
                "Example: 'Create snapshot daily-backup in filesystem gpfs01'"
            )

        snapshot_data = {"snapshotName": snapshot_name}

        if fileset:
            # Create fileset snapshot
            result = await self.call_tool(
                "create_fileset_snapshot",
                {
                    "filesystem": filesystem,
                    "fileset": fileset,
                    "snapshot_data": snapshot_data,
                },
                context_id,
            )
            return self.format_response(
                result, f"Created Snapshot: {snapshot_name} (fileset: {fileset})"
            )
        else:
            # Create filesystem snapshot
            result = await self.call_tool(
                "create_snapshot",
                {"filesystem": filesystem, "snapshot_data": snapshot_data},
                context_id,
            )
            return self.format_response(
                result, f"Created Snapshot: {snapshot_name}"
            )

    async def _delete_snapshot(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Delete a snapshot."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        # Extract snapshot name
        snapshot_match = re.search(
            r"snapshot\s+['\"]?(\S+)['\"]?", text.lower()
        )
        snapshot_name = snapshot_match.group(1) if snapshot_match else None

        if not filesystem or not snapshot_name:
            return (
                "Please specify both filesystem and snapshot name. "
                "Example: 'Delete snapshot old-backup in filesystem gpfs01'"
            )

        if fileset:
            result = await self.call_tool(
                "delete_fileset_snapshot",
                {
                    "filesystem": filesystem,
                    "fileset": fileset,
                    "snapshot_name": snapshot_name,
                },
                context_id,
            )
        else:
            result = await self.call_tool(
                "delete_snapshot",
                {"filesystem": filesystem, "snapshot_name": snapshot_name},
                context_id,
            )

        return self.format_response(result, f"Deleted Snapshot: {snapshot_name}")

    async def _start_nodes(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Start nodes."""
        node = self.extract_node(text)

        if not node:
            return (
                "Please specify which nodes to start. "
                "Example: 'Start node node1' or 'Start nodes node1,node2'"
            )

        nodes_data = {"nodes": node}

        result = await self.call_tool(
            "start_nodes",
            {"nodes_data": nodes_data},
            context_id,
        )
        return self.format_response(result, f"Started Nodes: {node}")

    async def _stop_nodes(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Stop nodes."""
        node = self.extract_node(text)

        if not node:
            return (
                "Please specify which nodes to stop. "
                "Example: 'Stop node node1'"
            )

        nodes_data = {"nodes": node}

        result = await self.call_tool(
            "stop_nodes",
            {"nodes_data": nodes_data},
            context_id,
        )
        return self.format_response(result, f"Stopped Nodes: {node}")

    async def _add_node(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Add a node to the cluster."""
        # This would require more complex parameter extraction
        return (
            "Adding nodes requires detailed configuration. "
            "Please provide node hostname and role. "
            "Example: 'Add node hostname=node3.example.com role=quorum'"
        )

    async def _handle_remote_cluster(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Handle remote cluster operations."""
        is_list = any(kw in text.lower() for kw in ["list", "show", "get", "all"])

        if is_list:
            result = await self.call_tool(
                "list_remote_clusters",
                {},
                context_id,
            )
            return self.format_response(result, "Remote Clusters")

        return (
            "Available remote cluster operations:\n"
            "• 'List remote clusters'\n"
            "• 'Add remote cluster <name>'\n"
            "• 'Delete remote cluster <name>'"
        )

    async def _list_nsds(self, context_id: str | None) -> str:
        """List all NSDs."""
        result = await self.call_tool(
            "list_nsds",
            {},
            context_id,
        )
        return self.format_response(result, "Network Shared Disks")

    async def _get_nsd(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get NSD details."""
        # Extract NSD name
        nsd_match = re.search(r"nsd\s+['\"]?(\S+)['\"]?", text.lower())
        nsd_name = nsd_match.group(1) if nsd_match else None

        if not nsd_name:
            return await self._list_nsds(context_id)

        result = await self.call_tool(
            "get_nsd",
            {"nsd_name": nsd_name},
            context_id,
        )
        return self.format_response(result, f"NSD: {nsd_name}")

    async def _create_nsd(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Create an NSD."""
        return (
            "Creating NSDs requires detailed configuration. "
            "Please provide disk device and servers. "
            "Example: 'Create NSD device=/dev/sdb servers=node1,node2'"
        )

    async def _delete_nsd(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Delete an NSD."""
        nsd_match = re.search(r"nsd\s+['\"]?(\S+)['\"]?", text.lower())
        nsd_name = nsd_match.group(1) if nsd_match else None

        if not nsd_name:
            return (
                "Please specify the NSD name. "
                "Example: 'Delete NSD nsd1'"
            )

        result = await self.call_tool(
            "delete_nsd",
            {"nsd_name": nsd_name},
            context_id,
        )
        return self.format_response(result, f"Deleted NSD: {nsd_name}")

    async def _get_config(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get configuration information."""
        user_lower = text.lower()

        if "admin" in user_lower:
            result = await self.call_tool("get_admin_config", {}, context_id)
            return self.format_response(result, "Admin Configuration")

        if "auth" in user_lower:
            result = await self.call_tool("get_auth_config", {}, context_id)
            return self.format_response(result, "Authentication Configuration")

        if "ces" in user_lower:
            result = await self.call_tool("get_ces_config", {}, context_id)
            return self.format_response(result, "CES Configuration")

        if "gui" in user_lower:
            result = await self.call_tool("get_gui_config", {}, context_id)
            return self.format_response(result, "GUI Configuration")

        # Default: admin config
        result = await self.call_tool("get_admin_config", {}, context_id)
        return self.format_response(result, "Admin Configuration")


def register_admin_agent(server: Server) -> None:
    """Register the Admin Agent with an AgentStack server.

    Args:
        server: The AgentStack server instance.
    """
    agent = AdminAgent()

    @server.register(
        name="admin_agent",
        description=agent.description,
    )
    async def admin_handler(context: RunContext, request: AgentMessage) -> str:
        """Handle cluster administration requests."""
        message = request.message
        context_id = getattr(context, "context_id", None)
        return await agent.process(message, context_id)
