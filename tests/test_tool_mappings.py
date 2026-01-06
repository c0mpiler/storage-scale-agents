"""Tests for tool mappings and configuration."""


from scale_agents.config.tool_mappings import (
    ADMIN_TOOLS,
    DESTRUCTIVE_TOOLS,
    HEALTH_TOOLS,
    HIGH_RISK_TOOLS,
    PERFORMANCE_TOOLS,
    STORAGE_TOOLS,
    AgentType,
    get_tool_risk_level,
    get_tools_for_agent,
    is_destructive_tool,
    is_high_risk_tool,
)


class TestToolMappings:
    """Tests for tool mapping functions."""

    def test_health_tools_are_read_only(self):
        """Health tools should not overlap with destructive tools."""
        overlap = HEALTH_TOOLS & DESTRUCTIVE_TOOLS
        assert len(overlap) == 0, f"Health tools should not be destructive: {overlap}"

    def test_performance_tools_are_read_only(self):
        """Performance tools should not overlap with destructive tools."""
        overlap = PERFORMANCE_TOOLS & DESTRUCTIVE_TOOLS
        assert len(overlap) == 0, f"Performance tools should not be destructive: {overlap}"

    def test_storage_tools_include_destructive(self):
        """Storage tools should include some destructive operations."""
        overlap = STORAGE_TOOLS & DESTRUCTIVE_TOOLS
        assert len(overlap) > 0, "Storage tools should include destructive operations"

    def test_admin_tools_include_destructive(self):
        """Admin tools should include many destructive operations."""
        overlap = ADMIN_TOOLS & DESTRUCTIVE_TOOLS
        assert len(overlap) > 0, "Admin tools should include destructive operations"

    def test_high_risk_tools_subset_of_destructive(self):
        """High risk tools should be a subset of destructive tools."""
        assert HIGH_RISK_TOOLS.issubset(DESTRUCTIVE_TOOLS), \
            "All high-risk tools should be classified as destructive"

    def test_get_tools_for_agent_health(self):
        """Should return health tools for health agent."""
        tools = get_tools_for_agent(AgentType.HEALTH)
        assert tools == HEALTH_TOOLS

    def test_get_tools_for_agent_invalid(self):
        """Should return empty set for invalid agent type."""
        tools = get_tools_for_agent("invalid")  # type: ignore
        assert tools == frozenset()

    def test_is_destructive_tool_true(self):
        """Should identify destructive tools correctly."""
        assert is_destructive_tool("delete_fileset") is True
        assert is_destructive_tool("create_fileset") is True
        assert is_destructive_tool("stop_nodes") is True

    def test_is_destructive_tool_false(self):
        """Should identify non-destructive tools correctly."""
        assert is_destructive_tool("list_filesystems") is False
        assert is_destructive_tool("get_nodes_status") is False
        assert is_destructive_tool("list_quotas") is False

    def test_is_high_risk_tool_true(self):
        """Should identify high-risk tools correctly."""
        assert is_high_risk_tool("delete_fileset") is True
        assert is_high_risk_tool("delete_filesystem") is True
        assert is_high_risk_tool("stop_nodes") is True

    def test_is_high_risk_tool_false(self):
        """Should identify non-high-risk tools correctly."""
        assert is_high_risk_tool("create_fileset") is False
        assert is_high_risk_tool("set_quota") is False

    def test_get_tool_risk_level_high(self):
        """Should return HIGH for high-risk tools."""
        assert get_tool_risk_level("delete_fileset") == "HIGH"
        assert get_tool_risk_level("unmount_filesystem") == "HIGH"

    def test_get_tool_risk_level_medium(self):
        """Should return MEDIUM for destructive but not high-risk tools."""
        assert get_tool_risk_level("create_fileset") == "MEDIUM"
        assert get_tool_risk_level("set_quota") == "MEDIUM"

    def test_get_tool_risk_level_low(self):
        """Should return LOW for non-destructive tools."""
        assert get_tool_risk_level("list_filesystems") == "LOW"
        assert get_tool_risk_level("get_nodes_status") == "LOW"
