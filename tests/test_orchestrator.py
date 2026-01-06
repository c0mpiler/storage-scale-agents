"""Tests for the Orchestrator agent."""


import pytest

from scale_agents.agents.orchestrator import (
    Intent,
    Orchestrator,
)


class TestIntentClassification:
    """Tests for intent classification."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator instance."""
        return Orchestrator()

    def test_classify_health_intent(self, orchestrator):
        """Should classify health-related queries."""
        test_cases = [
            "What is the health status of the cluster?",
            "Are there any unhealthy nodes?",
            "Show me node events",
            "Is there anything wrong with the cluster?",
            "Check cluster health",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.HEALTH, f"Failed for: {text}"

    def test_classify_storage_intent(self, orchestrator):
        """Should classify storage-related queries."""
        test_cases = [
            "List all filesystems",
            "Create fileset project-data",
            "Mount filesystem gpfs01",
            "Show filesets in gpfs01",
            "Delete fileset old-data",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.STORAGE, f"Failed for: {text}"

    def test_classify_quota_intent(self, orchestrator):
        """Should classify quota-related queries."""
        test_cases = [
            "Set quota for user1",
            "Show usage for fileset project-data",
            "List all quotas",
            "How much space is used?",
            "Delete quota for project-x",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.QUOTA, f"Failed for: {text}"

    def test_classify_performance_intent(self, orchestrator):
        """Should classify performance-related queries."""
        test_cases = [
            "Analyze performance bottlenecks",
            "Why is the cluster slow?",
            "Check IOPS on filesystem",
            "Investigate latency issues",
            "Show throughput metrics",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.PERFORMANCE, f"Failed for: {text}"

    def test_classify_admin_intent(self, orchestrator):
        """Should classify admin-related queries."""
        test_cases = [
            "Create snapshot daily-backup",
            "List all snapshots",
            "Start node node1",
            "Stop nodes for maintenance",
            "Show cluster configuration",
            "Add remote cluster",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.ADMIN, f"Failed for: {text}"

    def test_classify_help_intent(self, orchestrator):
        """Should classify help requests."""
        test_cases = [
            "Help me understand",
            "What can you do?",
            "Show me your capabilities",
            "How do I use this?",
        ]

        for text in test_cases:
            result = orchestrator._classify_intent(text)
            assert result.intent == Intent.HELP, f"Failed for: {text}"

    def test_classify_unknown_intent(self, orchestrator):
        """Should return unknown for unrecognized queries."""
        result = orchestrator._classify_intent("random gibberish xyz")
        assert result.intent == Intent.UNKNOWN


class TestOrchestratorHelp:
    """Tests for orchestrator help responses."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator instance."""
        return Orchestrator()

    def test_help_response_contains_sections(self, orchestrator):
        """Help response should contain all major sections."""
        response = orchestrator._get_help_response()

        assert "Health Monitoring" in response
        assert "Storage Management" in response
        assert "Quota Management" in response
        assert "Performance Analysis" in response
        assert "Administration" in response
        assert "Example Queries" in response

    def test_clarification_prompt(self, orchestrator):
        """Clarification prompt should list options."""
        response = orchestrator._get_clarification_prompt("some text")

        assert "Health" in response
        assert "Storage" in response
        assert "Quota" in response
        assert "Performance" in response
        assert "Admin" in response
