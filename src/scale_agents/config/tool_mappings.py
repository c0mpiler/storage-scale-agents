"""Tool mappings and capability definitions for Scale Agents.

This module defines which MCP tools each agent can access and which
operations require user confirmation before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class AgentType(str, Enum):
    """Enumeration of available agent types."""

    ORCHESTRATOR = "orchestrator"
    HEALTH = "health"
    STORAGE = "storage"
    QUOTA = "quota"
    PERFORMANCE = "performance"
    ADMIN = "admin"


@dataclass(frozen=True)
class AgentCapability:
    """Defines the capabilities and tool access for an agent."""

    agent_type: AgentType
    name: str
    description: str
    tools: frozenset[str]
    read_only: bool = True
    requires_elevated_access: bool = False
    personas: tuple[str, ...] = field(default_factory=tuple)


# Health Agent Tools - Read-only monitoring and diagnostics
HEALTH_TOOLS: Final[frozenset[str]] = frozenset([
    "get_node_health_states",
    "get_node_health_events",
    "get_filesystem_health_states",
    "get_filesystem_health_events",
    "get_nodes_status",
    "get_nodes_config",
    "list_clusters",
    "get_node_version",
    "get_version",
])

# Storage Agent Tools - Filesystem and fileset management
STORAGE_TOOLS: Final[frozenset[str]] = frozenset([
    # Read operations
    "list_filesystems",
    "get_filesystem",
    "list_filesets",
    "get_fileset",
    "list_storage_pools",
    "get_storage_pool",
    # Write operations (require confirmation)
    "create_fileset",
    "delete_fileset",
    "update_fileset",
    "link_fileset",
    "unlink_fileset",
    "mount_filesystem",
    "unmount_filesystem",
    "mount_all_filesystems",
    "unmount_all_filesystems",
    "update_storage_pool",
])

# Quota Agent Tools - Capacity management
QUOTA_TOOLS: Final[frozenset[str]] = frozenset([
    # Read operations
    "list_quotas",
    "get_fileset_usage",
    # Write operations (require confirmation)
    "set_quota",
    "delete_quota",
])

# Performance Agent Tools - Read-only performance analysis
PERFORMANCE_TOOLS: Final[frozenset[str]] = frozenset([
    "get_filesystem_health_states",
    "get_node_health_states",
    "get_node_health_events",
    "get_nodes_status",
    "get_nodes_config",
    "list_storage_pools",
    "get_storage_pool",
    "get_fileset_usage",
    "list_filesystems",
    "get_filesystem",
])

# Admin Agent Tools - Cluster administration
ADMIN_TOOLS: Final[frozenset[str]] = frozenset([
    # Read operations
    "list_clusters",
    "list_remote_clusters",
    "get_remote_cluster",
    "list_cluster_trust",
    "list_snapshots",
    "get_snapshot",
    "get_snapdir_settings",
    "list_fileset_snapshots",
    "get_fileset_snapshot",
    "get_admin_config",
    "get_auth_config",
    "get_ces_config",
    "get_gui_config",
    "list_nsds",
    "get_nsd",
    "get_policy",
    # Write operations (require confirmation)
    "create_cluster",
    "update_cluster_manager",
    "add_remote_cluster",
    "delete_remote_cluster",
    "update_remote_cluster",
    "refresh_remote_cluster",
    "authorize_cluster",
    "unauthorize_cluster",
    "add_node",
    "batch_add_nodes",
    "start_nodes",
    "stop_nodes",
    "create_snapshot",
    "delete_snapshot",
    "batch_delete_snapshots",
    "create_fileset_snapshot",
    "delete_fileset_snapshot",
    "batch_create_fileset_snapshots",
    "batch_delete_fileset_snapshots",
    "update_admin_config",
    "update_auth_config",
    "update_ces_config",
    "update_gui_config",
    "create_nsd",
    "delete_nsd",
    "update_nsd",
    "batch_create_nsds",
    "batch_delete_nsds",
    "update_policy",
    "delete_filesystem",
])

# Destructive operations requiring explicit confirmation
DESTRUCTIVE_TOOLS: Final[frozenset[str]] = frozenset([
    # Fileset operations
    "create_fileset",
    "delete_fileset",
    "update_fileset",
    "link_fileset",
    "unlink_fileset",
    # Filesystem operations
    "mount_filesystem",
    "unmount_filesystem",
    "mount_all_filesystems",
    "unmount_all_filesystems",
    "delete_filesystem",
    # Quota operations
    "set_quota",
    "delete_quota",
    # Cluster operations
    "create_cluster",
    "update_cluster_manager",
    "add_remote_cluster",
    "delete_remote_cluster",
    "update_remote_cluster",
    "authorize_cluster",
    "unauthorize_cluster",
    # Node operations
    "add_node",
    "batch_add_nodes",
    "start_nodes",
    "stop_nodes",
    # Snapshot operations
    "create_snapshot",
    "delete_snapshot",
    "batch_delete_snapshots",
    "create_fileset_snapshot",
    "delete_fileset_snapshot",
    "batch_create_fileset_snapshots",
    "batch_delete_fileset_snapshots",
    # NSD operations
    "create_nsd",
    "delete_nsd",
    "update_nsd",
    "batch_create_nsds",
    "batch_delete_nsds",
    # Configuration operations
    "update_admin_config",
    "update_auth_config",
    "update_ces_config",
    "update_gui_config",
    "update_policy",
    "update_storage_pool",
])

# High-risk operations that can cause data loss
HIGH_RISK_TOOLS: Final[frozenset[str]] = frozenset([
    "delete_fileset",
    "delete_filesystem",
    "delete_snapshot",
    "batch_delete_snapshots",
    "delete_fileset_snapshot",
    "batch_delete_fileset_snapshots",
    "delete_nsd",
    "batch_delete_nsds",
    "delete_remote_cluster",
    "unmount_filesystem",
    "unmount_all_filesystems",
    "stop_nodes",
])

# Agent capability definitions
AGENT_CAPABILITIES: Final[dict[AgentType, AgentCapability]] = {
    AgentType.HEALTH: AgentCapability(
        agent_type=AgentType.HEALTH,
        name="Health Agent",
        description="Monitors cluster health, node status, and filesystem health events",
        tools=HEALTH_TOOLS,
        read_only=True,
        requires_elevated_access=False,
        personas=("SRE", "NOC Operator", "System Administrator"),
    ),
    AgentType.STORAGE: AgentCapability(
        agent_type=AgentType.STORAGE,
        name="Storage Agent",
        description="Manages filesystems, filesets, and storage pools",
        tools=STORAGE_TOOLS,
        read_only=False,
        requires_elevated_access=False,
        personas=("Storage Administrator", "DevOps Engineer"),
    ),
    AgentType.QUOTA: AgentCapability(
        agent_type=AgentType.QUOTA,
        name="Quota Agent",
        description="Manages quotas and monitors capacity usage",
        tools=QUOTA_TOOLS,
        read_only=False,
        requires_elevated_access=False,
        personas=("Storage Administrator", "Project Lead", "Capacity Planner"),
    ),
    AgentType.PERFORMANCE: AgentCapability(
        agent_type=AgentType.PERFORMANCE,
        name="Performance Agent",
        description="Analyzes performance metrics and identifies bottlenecks",
        tools=PERFORMANCE_TOOLS,
        read_only=True,
        requires_elevated_access=False,
        personas=("Performance Engineer", "SRE", "Capacity Planner"),
    ),
    AgentType.ADMIN: AgentCapability(
        agent_type=AgentType.ADMIN,
        name="Admin Agent",
        description="Cluster administration, node management, and snapshot operations",
        tools=ADMIN_TOOLS,
        read_only=False,
        requires_elevated_access=True,
        personas=("Cluster Administrator", "Infrastructure Lead"),
    ),
}


def get_tools_for_agent(agent_type: AgentType) -> frozenset[str]:
    """Get the set of tools available for a specific agent type."""
    capability = AGENT_CAPABILITIES.get(agent_type)
    if capability is None:
        return frozenset()
    return capability.tools


def is_destructive_tool(tool_name: str) -> bool:
    """Check if a tool is classified as destructive."""
    return tool_name in DESTRUCTIVE_TOOLS


def is_high_risk_tool(tool_name: str) -> bool:
    """Check if a tool is classified as high-risk."""
    return tool_name in HIGH_RISK_TOOLS


def get_tool_risk_level(tool_name: str) -> str:
    """Get the risk level classification for a tool."""
    if tool_name in HIGH_RISK_TOOLS:
        return "HIGH"
    if tool_name in DESTRUCTIVE_TOOLS:
        return "MEDIUM"
    return "LOW"
