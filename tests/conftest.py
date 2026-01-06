"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client for testing."""
    with patch("scale_agents.tools.mcp_client.MCPClient") as MockClient:
        instance = AsyncMock()
        instance.call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": '{"status": "ok"}'}]
        })
        instance.connect = AsyncMock()
        instance.disconnect = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        MockClient.return_value = instance
        yield instance


@pytest.fixture
def sample_health_response():
    """Sample health response for testing."""
    return {
        "content": [{
            "type": "text",
            "text": '{"states": [{"entityName": "node1", "status": "HEALTHY"}]}'
        }]
    }


@pytest.fixture
def sample_filesystem_response():
    """Sample filesystem list response for testing."""
    return {
        "content": [{
            "type": "text",
            "text": '{"filesystems": [{"filesystemName": "gpfs01", "status": "mounted"}]}'
        }]
    }


@pytest.fixture
def sample_fileset_response():
    """Sample fileset list response for testing."""
    return {
        "content": [{
            "type": "text",
            "text": '{"filesets": [{"filesetName": "root", "status": "Linked"}]}'
        }]
    }


@pytest.fixture
def sample_quota_response():
    """Sample quota list response for testing."""
    return {
        "content": [{
            "type": "text",
            "text": '{"quotas": [{"objectName": "user1", "blockUsage": 1000, "blockHardLimit": 5000}]}'
        }]
    }


@pytest.fixture
def sample_snapshot_response():
    """Sample snapshot list response for testing."""
    return {
        "content": [{
            "type": "text",
            "text": '{"snapshots": [{"snapshotName": "daily-backup", "status": "Valid"}]}'
        }]
    }
