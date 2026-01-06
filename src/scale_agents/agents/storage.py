"""Storage Agent for filesystem and fileset management.

This agent handles filesystem and fileset lifecycle operations,
including creation, deletion, mounting, and linking.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.config.tool_mappings import STORAGE_TOOLS

if TYPE_CHECKING:
    from a2a.types import Message
    from agentstack_sdk.a2a.types import AgentMessage
    from agentstack_sdk.server import Server
    from agentstack_sdk.server.context import RunContext


class StorageAgent(BaseScaleAgent):
    """Agent for filesystem and fileset management.

    Capabilities:
    - List and inspect filesystems
    - Create, delete, and update filesets
    - Link and unlink filesets
    - Mount and unmount filesystems
    - Manage storage pools

    Destructive operations require user confirmation.
    """

    def __init__(self) -> None:
        super().__init__(
            name="storage",
            description=(
                "Manages filesystems, filesets, and storage pools. "
                "Handles lifecycle operations for storage administrators."
            ),
            allowed_tools=STORAGE_TOOLS,
            read_only=False,
        )

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process a storage management request.

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
            is_create = any(kw in user_lower for kw in ["create", "add", "new", "make"])
            is_delete = any(kw in user_lower for kw in ["delete", "remove", "destroy"])
            is_list = any(kw in user_lower for kw in ["list", "show", "get", "all"])
            is_mount = "mount" in user_lower
            is_unmount = any(kw in user_lower for kw in ["unmount", "umount"])
            is_link = "link" in user_lower and "unlink" not in user_lower
            is_unlink = "unlink" in user_lower

            # Determine target type
            is_fileset = any(kw in user_lower for kw in ["fileset", "filesets"])
            is_filesystem = any(kw in user_lower for kw in ["filesystem", "filesystems", " fs "])
            is_pool = any(kw in user_lower for kw in ["pool", "pools", "storage pool"])

            # Route to appropriate handler
            if is_pool:
                if is_list:
                    return await self._list_storage_pools(user_text, context_id)
                return await self._get_storage_pool(user_text, context_id)

            if is_fileset:
                if is_create:
                    return await self._create_fileset(user_text, context_id)
                if is_delete:
                    return await self._delete_fileset(user_text, context_id)
                if is_link:
                    return await self._link_fileset(user_text, context_id)
                if is_unlink:
                    return await self._unlink_fileset(user_text, context_id)
                if is_list:
                    return await self._list_filesets(user_text, context_id)
                return await self._get_fileset(user_text, context_id)

            if is_filesystem:
                if is_mount:
                    return await self._mount_filesystem(user_text, context_id)
                if is_unmount:
                    return await self._unmount_filesystem(user_text, context_id)
                if is_list:
                    return await self._list_filesystems(context_id)
                return await self._get_filesystem(user_text, context_id)

            # Default: list filesystems
            return await self._list_filesystems(context_id)

        except Exception as e:
            return await self.handle_error(e, "storage operation")

    async def _list_filesystems(self, context_id: str | None) -> str:
        """List all filesystems."""
        result = await self.call_tool(
            "list_filesystems",
            {},
            context_id,
        )
        return self.format_response(result, "Available Filesystems")

    async def _get_filesystem(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get filesystem details."""
        filesystem = self.extract_filesystem(text)
        if not filesystem:
            return await self._list_filesystems(context_id)

        result = await self.call_tool(
            "get_filesystem",
            {"filesystem": filesystem},
            context_id,
        )
        return self.format_response(result, f"Filesystem: {filesystem}")

    async def _list_filesets(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """List filesets in a filesystem."""
        filesystem = self.extract_filesystem(text)
        if not filesystem:
            return (
                "Please specify a filesystem. "
                "Example: 'List filesets in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "list_filesets",
            {"filesystem": filesystem},
            context_id,
        )
        return self.format_response(result, f"Filesets in {filesystem}")

    async def _get_fileset(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get fileset details."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem or not fileset:
            return (
                "Please specify both filesystem and fileset names. "
                "Example: 'Show fileset user-homes in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "get_fileset",
            {"filesystem": filesystem, "fileset_name": fileset},
            context_id,
        )
        return self.format_response(result, f"Fileset: {fileset}")

    async def _create_fileset(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Create a new fileset."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Create fileset project-data in filesystem gpfs01'"
            )

        if not fileset:
            # Try to extract from different patterns
            match = re.search(r"create\s+(?:fileset\s+)?['\"]?(\S+)['\"]?", text.lower())
            if match:
                fileset = match.group(1)
            else:
                return (
                    "Please specify the fileset name. "
                    "Example: 'Create fileset project-data in filesystem gpfs01'"
                )

        fileset_data = {
            "filesetName": fileset,
        }

        result = await self.call_tool(
            "create_fileset",
            {"filesystem": filesystem, "fileset_data": fileset_data},
            context_id,
        )
        return self.format_response(result, f"Created Fileset: {fileset}")

    async def _delete_fileset(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Delete a fileset."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem or not fileset:
            return (
                "Please specify both filesystem and fileset names. "
                "Example: 'Delete fileset old-data in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "delete_fileset",
            {"filesystem": filesystem, "fileset_name": fileset},
            context_id,
        )
        return self.format_response(result, f"Deleted Fileset: {fileset}")

    async def _link_fileset(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Link a fileset to a junction path."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem or not fileset:
            return (
                "Please specify both filesystem and fileset names. "
                "Example: 'Link fileset project-data in filesystem gpfs01 to /gpfs01/projects'"
            )

        # Extract junction path
        path_match = re.search(r"(?:to|at|path)\s+['\"]?(/\S+)['\"]?", text.lower())
        junction_path = path_match.group(1) if path_match else None

        if not junction_path:
            return (
                "Please specify the junction path. "
                "Example: 'Link fileset project-data to /gpfs01/projects'"
            )

        link_data = {"path": junction_path}

        result = await self.call_tool(
            "link_fileset",
            {
                "filesystem": filesystem,
                "fileset_name": fileset,
                "link_data": link_data,
            },
            context_id,
        )
        return self.format_response(
            result, f"Linked Fileset: {fileset} -> {junction_path}"
        )

    async def _unlink_fileset(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Unlink a fileset from its junction path."""
        filesystem = self.extract_filesystem(text)
        fileset = self.extract_fileset(text)

        if not filesystem or not fileset:
            return (
                "Please specify both filesystem and fileset names. "
                "Example: 'Unlink fileset project-data in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "unlink_fileset",
            {"filesystem": filesystem, "fileset_name": fileset},
            context_id,
        )
        return self.format_response(result, f"Unlinked Fileset: {fileset}")

    async def _mount_filesystem(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Mount a filesystem."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Mount filesystem gpfs01'"
            )

        # Check for specific nodes
        node = self.extract_node(text)
        args: dict = {"filesystem": filesystem}
        if node:
            args["nodes"] = node

        result = await self.call_tool(
            "mount_filesystem",
            args,
            context_id,
        )

        title = f"Mounted: {filesystem}"
        if node:
            title += f" on {node}"
        return self.format_response(result, title)

    async def _unmount_filesystem(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Unmount a filesystem."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'Unmount filesystem gpfs01'"
            )

        node = self.extract_node(text)
        args: dict = {"filesystem": filesystem}
        if node:
            args["nodes"] = node

        result = await self.call_tool(
            "unmount_filesystem",
            args,
            context_id,
        )

        title = f"Unmounted: {filesystem}"
        if node:
            title += f" from {node}"
        return self.format_response(result, title)

    async def _list_storage_pools(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """List storage pools for a filesystem."""
        filesystem = self.extract_filesystem(text)

        if not filesystem:
            return (
                "Please specify the filesystem. "
                "Example: 'List storage pools in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "list_storage_pools",
            {"filesystem": filesystem},
            context_id,
        )
        return self.format_response(result, f"Storage Pools: {filesystem}")

    async def _get_storage_pool(
        self,
        text: str,
        context_id: str | None,
    ) -> str:
        """Get storage pool details."""
        filesystem = self.extract_filesystem(text)

        # Extract pool name
        pool_match = re.search(r"pool\s+['\"]?(\S+)['\"]?", text.lower())
        pool_name = pool_match.group(1) if pool_match else None

        if not filesystem or not pool_name:
            return (
                "Please specify both filesystem and pool names. "
                "Example: 'Show storage pool system in filesystem gpfs01'"
            )

        result = await self.call_tool(
            "get_storage_pool",
            {"filesystem": filesystem, "pool_name": pool_name},
            context_id,
        )
        return self.format_response(result, f"Storage Pool: {pool_name}")


def register_storage_agent(server: Server) -> None:
    """Register the Storage Agent with an AgentStack server.

    Args:
        server: The AgentStack server instance.
    """
    agent = StorageAgent()

    @server.register(
        name="storage_agent",
        description=agent.description,
    )
    async def storage_handler(context: RunContext, request: AgentMessage) -> str:
        """Handle storage management requests."""
        message = request.message
        context_id = getattr(context, "context_id", None)
        return await agent.process(message, context_id)
