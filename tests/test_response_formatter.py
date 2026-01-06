"""Tests for response formatting utilities."""


from scale_agents.tools.response_formatter import (
    format_error_response,
    format_health_response,
    format_list_response,
    format_response,
)


class TestFormatResponse:
    """Tests for format_response function."""

    def test_format_string(self):
        """Should format string content."""
        result = format_response("Test message", "Test Title")
        assert "Test Title" in result
        assert "Test message" in result

    def test_format_dict(self):
        """Should format dict content."""
        data = {"key1": "value1", "key2": 123}
        result = format_response(data, "Dict Test")
        assert "Dict Test" in result
        assert "key1" in result
        assert "value1" in result

    def test_format_list(self):
        """Should format list content."""
        data = ["item1", "item2", "item3"]
        result = format_response(data, "List Test")
        assert "List Test" in result
        assert "3 item" in result

    def test_format_mcp_response(self):
        """Should extract content from MCP response format."""
        data = {
            "content": [{"type": "text", "text": '{"status": "ok"}'}]
        }
        result = format_response(data, "MCP Test")
        assert "MCP Test" in result
        assert "status" in result


class TestFormatErrorResponse:
    """Tests for format_error_response function."""

    def test_format_string_error(self):
        """Should format string error."""
        result = format_error_response("Something went wrong")
        assert "Error" in result
        assert "Something went wrong" in result

    def test_format_exception_error(self):
        """Should format exception error."""
        error = ValueError("Test error message")
        result = format_error_response(error)
        assert "Error" in result
        assert "Test error message" in result

    def test_format_with_context(self):
        """Should include context when provided."""
        result = format_error_response("Error occurred", "During file processing")
        assert "Error" in result
        assert "Error occurred" in result
        assert "Context" in result
        assert "During file processing" in result


class TestFormatListResponse:
    """Tests for format_list_response function."""

    def test_empty_list(self):
        """Should show empty message for empty list."""
        result = format_list_response(
            [],
            "Empty List",
            empty_message="Nothing here",
        )
        assert "Empty List" in result
        assert "Nothing here" in result

    def test_list_with_items(self):
        """Should list items."""
        items = [
            {"name": "item1", "status": "active"},
            {"name": "item2", "status": "inactive"},
        ]
        result = format_list_response(items, "Items")
        assert "Items" in result
        assert "2 item" in result
        assert "item1" in result
        assert "item2" in result

    def test_list_truncation(self):
        """Should truncate long lists."""
        items = [{"name": f"item{i}"} for i in range(100)]
        result = format_list_response(items, "Many Items", max_items=10)
        assert "Many Items" in result
        assert "100 item" in result
        assert "90 more" in result


class TestFormatHealthResponse:
    """Tests for format_health_response function."""

    def test_healthy_states(self):
        """Should format healthy states."""
        data = {
            "states": [
                {"entityName": "node1", "status": "HEALTHY"},
                {"entityName": "node2", "status": "HEALTHY"},
            ]
        }
        result = format_health_response(data, "Health Status")
        assert "Health Status" in result
        assert "healthy" in result.lower()

    def test_critical_states(self):
        """Should highlight critical states."""
        data = {
            "states": [
                {"entityName": "node1", "status": "CRITICAL", "message": "Disk failure"},
            ]
        }
        result = format_health_response(data, "Health Status")
        assert "Health Status" in result
        assert "critical" in result.lower()

    def test_mixed_states(self):
        """Should show summary of mixed states."""
        data = {
            "states": [
                {"entityName": "node1", "status": "HEALTHY"},
                {"entityName": "node2", "status": "WARNING"},
                {"entityName": "node3", "status": "CRITICAL"},
            ]
        }
        result = format_health_response(data, "Health Status")
        assert "Health Status" in result
        # Should have count indicators
        assert "1" in result

    def test_empty_states(self):
        """Should show all healthy message for empty states."""
        data = {"states": []}
        result = format_health_response(data, "Health Status")
        assert "Health Status" in result
        assert "healthy" in result.lower() or "no issues" in result.lower()
