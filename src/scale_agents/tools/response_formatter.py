"""Response formatting utilities for Scale Agents.

Provides consistent formatting of MCP tool responses for display to users.
"""

from __future__ import annotations

import json
from typing import Any

import orjson


def format_response(
    data: Any,
    title: str | None = None,
    max_items: int = 50,
) -> str:
    """Format a generic response for display.

    Args:
        data: The data to format.
        title: Optional title for the response.
        max_items: Maximum items to display in lists.

    Returns:
        Formatted string response.
    """
    lines: list[str] = []

    if title:
        lines.append(f"**{title}**")
        lines.append("")

    content = _extract_content(data)

    if isinstance(content, str):
        lines.append(content)
    elif isinstance(content, dict):
        lines.append(_format_dict(content, indent=0))
    elif isinstance(content, list):
        lines.append(_format_list(content, max_items=max_items))
    else:
        lines.append(str(content))

    return "\n".join(lines)


def format_error_response(
    error: str | Exception,
    context: str | None = None,
) -> str:
    """Format an error response for display.

    Args:
        error: The error message or exception.
        context: Optional context about what failed.

    Returns:
        Formatted error string.
    """
    lines = ["**❌ Error**", ""]

    if context:
        lines.append(f"**Context:** {context}")
        lines.append("")

    error_msg = str(error)
    lines.append(f"**Details:** {error_msg}")

    return "\n".join(lines)


def format_list_response(
    items: list[Any],
    title: str,
    item_formatter: Any | None = None,
    empty_message: str = "No items found.",
    max_items: int = 50,
) -> str:
    """Format a list response with optional custom formatting.

    Args:
        items: List of items to format.
        title: Title for the response.
        item_formatter: Optional callable to format each item.
        empty_message: Message to show when list is empty.
        max_items: Maximum items to display.

    Returns:
        Formatted list string.
    """
    lines = [f"**{title}**", ""]

    if not items:
        lines.append(empty_message)
        return "\n".join(lines)

    lines.append(f"*Found {len(items)} item(s)*")
    lines.append("")

    displayed = items[:max_items]
    for idx, item in enumerate(displayed, 1):
        if item_formatter:
            formatted = item_formatter(item)
        else:
            formatted = _format_list_item(item)
        lines.append(f"{idx}. {formatted}")

    if len(items) > max_items:
        lines.append("")
        lines.append(f"*... and {len(items) - max_items} more items*")

    return "\n".join(lines)


def format_health_response(
    data: Any,
    title: str,
    show_details: bool = True,
) -> str:
    """Format health-related data for display.

    Args:
        data: Health data to format.
        title: Title for the response.
        show_details: Whether to show detailed information.

    Returns:
        Formatted health response string.
    """
    lines = [f"**{title}**", ""]

    content = _extract_content(data)

    if isinstance(content, str):
        lines.append(content)
        return "\n".join(lines)

    # Try to parse health states/events
    if isinstance(content, dict):
        states = content.get("states", content.get("events", []))
        if isinstance(states, list):
            return _format_health_states(states, title, show_details)

        # Generic dict formatting
        lines.append(_format_dict(content, indent=0))

    elif isinstance(content, list):
        return _format_health_states(content, title, show_details)

    else:
        lines.append(str(content))

    return "\n".join(lines)


def _format_health_states(
    states: list[Any],
    title: str,
    show_details: bool,
) -> str:
    """Format a list of health states."""
    lines = [f"**{title}**", ""]

    if not states:
        lines.append("✅ No issues detected. All systems healthy.")
        return "\n".join(lines)

    # Group by status
    critical = []
    warning = []
    healthy = []
    unknown = []

    for state in states:
        if isinstance(state, dict):
            status = state.get("status", state.get("severity", "")).upper()
            if status in ("CRITICAL", "ERROR", "UNHEALTHY"):
                critical.append(state)
            elif status in ("WARNING", "DEGRADED"):
                warning.append(state)
            elif status in ("HEALTHY", "OK", "NORMAL"):
                healthy.append(state)
            else:
                unknown.append(state)
        else:
            unknown.append(state)

    # Summary line
    summary_parts = []
    if critical:
        summary_parts.append(f"🔴 {len(critical)} critical")
    if warning:
        summary_parts.append(f"🟡 {len(warning)} warning")
    if healthy:
        summary_parts.append(f"🟢 {len(healthy)} healthy")
    if unknown:
        summary_parts.append(f"⚪ {len(unknown)} unknown")

    lines.append(" | ".join(summary_parts))
    lines.append("")

    # Details
    if show_details:
        if critical:
            lines.append("**Critical Issues:**")
            for state in critical[:10]:
                lines.append(f"  • {_format_health_item(state)}")
            lines.append("")

        if warning:
            lines.append("**Warnings:**")
            for state in warning[:10]:
                lines.append(f"  • {_format_health_item(state)}")
            lines.append("")

    return "\n".join(lines)


def _format_health_item(item: dict[str, Any]) -> str:
    """Format a single health item."""
    parts = []

    # Entity identification
    entity = item.get("entityName", item.get("name", item.get("node", "")))
    if entity:
        parts.append(f"`{entity}`")

    # Status
    status = item.get("status", item.get("severity", ""))
    if status:
        parts.append(f"[{status}]")

    # Message/Description
    message = item.get("message", item.get("description", item.get("reason", "")))
    if message:
        parts.append(message)

    return " ".join(parts) if parts else str(item)


def _extract_content(data: Any) -> Any:
    """Extract the actual content from an MCP response."""
    if isinstance(data, dict):
        # Standard MCP response format
        if "content" in data:
            content = data["content"]
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    # Try to parse as JSON
                    try:
                        return orjson.loads(first["text"])
                    except (orjson.JSONDecodeError, TypeError):
                        return first["text"]
                return first
            return content

        # Direct data
        if "data" in data:
            return data["data"]

        # Result wrapper
        if "result" in data:
            return data["result"]

    return data


def _format_dict(d: dict[str, Any], indent: int = 0) -> str:
    """Format a dictionary for display."""
    lines = []
    prefix = "  " * indent

    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}:**")
            lines.append(_format_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}:** ({len(value)} items)")
            if len(value) <= 5:
                for item in value:
                    lines.append(f"{prefix}  • {_format_value(item)}")
        else:
            lines.append(f"{prefix}**{key}:** {_format_value(value)}")

    return "\n".join(lines)


def _format_list(items: list[Any], max_items: int = 50) -> str:
    """Format a list for display."""
    if not items:
        return "*Empty list*"

    lines = [f"*{len(items)} item(s)*", ""]

    for idx, item in enumerate(items[:max_items], 1):
        lines.append(f"{idx}. {_format_list_item(item)}")

    if len(items) > max_items:
        lines.append(f"*... and {len(items) - max_items} more*")

    return "\n".join(lines)


def _format_list_item(item: Any) -> str:
    """Format a single list item."""
    if isinstance(item, dict):
        # Try to find a name/identifier
        name = item.get("name", item.get("filesetName", item.get("filesystemName", "")))
        if name:
            status = item.get("status", item.get("state", ""))
            if status:
                return f"`{name}` ({status})"
            return f"`{name}`"
        # Compact dict representation
        return ", ".join(f"{k}={_format_value(v)}" for k, v in list(item.items())[:4])
    return str(item)


def _format_value(value: Any) -> str:
    """Format a single value for display."""
    if value is None:
        return "*none*"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if len(value) > 100:
            return f"{value[:97]}..."
        return value
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{{len(value)} fields}}"
    return str(value)
