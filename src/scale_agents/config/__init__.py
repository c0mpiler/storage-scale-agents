"""Configuration package for Scale Agents."""

from scale_agents.config.settings import settings
from scale_agents.config.tool_mappings import (
    ADMIN_TOOLS,
    DESTRUCTIVE_TOOLS,
    HEALTH_TOOLS,
    PERFORMANCE_TOOLS,
    QUOTA_TOOLS,
    STORAGE_TOOLS,
    AgentCapability,
)

__all__ = [
    "ADMIN_TOOLS",
    "DESTRUCTIVE_TOOLS",
    "HEALTH_TOOLS",
    "PERFORMANCE_TOOLS",
    "QUOTA_TOOLS",
    "STORAGE_TOOLS",
    "AgentCapability",
    "settings",
]
