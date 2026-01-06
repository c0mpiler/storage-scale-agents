"""Confirmation handling for destructive operations.

This module provides mechanisms to require and verify user confirmation
before executing potentially dangerous operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from scale_agents.config.tool_mappings import (
    DESTRUCTIVE_TOOLS,
    HIGH_RISK_TOOLS,
    get_tool_risk_level,
)
from scale_agents.config.settings import settings
from scale_agents.core.exceptions import ConfirmationRequiredError
from scale_agents.core.logging import get_logger

logger = get_logger(__name__)


class ConfirmationStatus(str, Enum):
    """Status of a confirmation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class ConfirmationState:
    """Tracks the state of a pending confirmation request."""

    tool_name: str
    arguments: dict[str, Any]
    risk_level: str
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    confirmation_code: str | None = None

    def is_expired(self) -> bool:
        """Check if the confirmation request has expired."""
        return datetime.now() > self.expires_at

    def confirm(self, code: str | None = None) -> bool:
        """Mark the request as confirmed.

        Args:
            code: Optional confirmation code to verify.

        Returns:
            True if confirmation succeeded, False otherwise.
        """
        if self.is_expired():
            self.status = ConfirmationStatus.EXPIRED
            return False

        if self.confirmation_code and code != self.confirmation_code:
            return False

        self.status = ConfirmationStatus.CONFIRMED
        return True

    def cancel(self) -> None:
        """Mark the request as cancelled."""
        self.status = ConfirmationStatus.CANCELLED


# In-memory store for pending confirmations (per conversation)
# In production, this would be backed by Redis or similar
_pending_confirmations: dict[str, ConfirmationState] = {}


def requires_confirmation(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Check if a tool call requires confirmation.

    Args:
        tool_name: Name of the tool being called.
        arguments: Arguments for the tool call.

    Returns:
        True if confirmation is required, False otherwise.
    """
    if not settings.require_confirmation:
        return False

    return tool_name in DESTRUCTIVE_TOOLS


def check_confirmation(
    tool_name: str,
    arguments: dict[str, Any],
    context_id: str | None = None,
    force_confirm: bool = False,
) -> ConfirmationState | None:
    """Check confirmation status and raise if confirmation is needed.

    Args:
        tool_name: Name of the tool being called.
        arguments: Arguments for the tool call.
        context_id: Optional conversation/context ID for tracking.
        force_confirm: If True, bypass confirmation requirements.

    Returns:
        ConfirmationState if there's a pending/completed confirmation,
        None if no confirmation is needed.

    Raises:
        ConfirmationRequiredError: If confirmation is required but not yet given.
    """
    if force_confirm or not requires_confirmation(tool_name, arguments):
        return None

    # Generate a key for this specific operation
    confirmation_key = _generate_confirmation_key(tool_name, arguments, context_id)

    # Check for existing confirmation
    existing = _pending_confirmations.get(confirmation_key)
    if existing:
        if existing.status == ConfirmationStatus.CONFIRMED and not existing.is_expired():
            logger.info(
                "operation_confirmed",
                tool_name=tool_name,
                context_id=context_id,
            )
            # Clear the confirmation after use
            del _pending_confirmations[confirmation_key]
            return existing

        if existing.is_expired():
            existing.status = ConfirmationStatus.EXPIRED
            del _pending_confirmations[confirmation_key]

    # Create new pending confirmation
    risk_level = get_tool_risk_level(tool_name)
    state = ConfirmationState(
        tool_name=tool_name,
        arguments=arguments,
        risk_level=risk_level,
    )
    _pending_confirmations[confirmation_key] = state

    logger.info(
        "confirmation_required",
        tool_name=tool_name,
        risk_level=risk_level,
        context_id=context_id,
    )

    raise ConfirmationRequiredError(
        tool_name=tool_name,
        arguments=arguments,
        risk_level=risk_level,
    )


def process_confirmation(
    context_id: str,
    user_response: str,
) -> tuple[bool, str]:
    """Process a user's confirmation response.

    Args:
        context_id: The conversation/context ID.
        user_response: The user's response text.

    Returns:
        Tuple of (success, message).
    """
    user_response_lower = user_response.lower().strip()

    # Find pending confirmation for this context
    pending_key = None
    pending_state = None

    for key, state in _pending_confirmations.items():
        if key.startswith(f"{context_id}:") and state.status == ConfirmationStatus.PENDING:
            pending_key = key
            pending_state = state
            break

    if not pending_state:
        return False, "No pending operation requires confirmation."

    if pending_state.is_expired():
        pending_state.status = ConfirmationStatus.EXPIRED
        del _pending_confirmations[pending_key]
        return False, "The confirmation request has expired. Please retry the operation."

    # Check for confirmation keywords
    confirm_keywords = {"confirm", "yes", "proceed", "ok", "approve", "y"}
    cancel_keywords = {"cancel", "no", "abort", "stop", "n"}

    if any(kw in user_response_lower for kw in confirm_keywords):
        pending_state.confirm()
        logger.info(
            "user_confirmed_operation",
            tool_name=pending_state.tool_name,
            context_id=context_id,
        )
        return True, f"Operation `{pending_state.tool_name}` confirmed. Proceeding..."

    if any(kw in user_response_lower for kw in cancel_keywords):
        pending_state.cancel()
        del _pending_confirmations[pending_key]
        logger.info(
            "user_cancelled_operation",
            tool_name=pending_state.tool_name,
            context_id=context_id,
        )
        return False, f"Operation `{pending_state.tool_name}` cancelled."

    return False, "Please reply 'confirm' to proceed or 'cancel' to abort."


def clear_pending_confirmations(context_id: str) -> int:
    """Clear all pending confirmations for a context.

    Args:
        context_id: The conversation/context ID.

    Returns:
        Number of confirmations cleared.
    """
    keys_to_remove = [
        key for key in _pending_confirmations if key.startswith(f"{context_id}:")
    ]
    for key in keys_to_remove:
        del _pending_confirmations[key]
    return len(keys_to_remove)


def get_pending_confirmation(context_id: str) -> ConfirmationState | None:
    """Get the pending confirmation for a context if any.

    Args:
        context_id: The conversation/context ID.

    Returns:
        The pending ConfirmationState or None.
    """
    for key, state in _pending_confirmations.items():
        if key.startswith(f"{context_id}:") and state.status == ConfirmationStatus.PENDING:
            return state
    return None


def _generate_confirmation_key(
    tool_name: str,
    arguments: dict[str, Any],
    context_id: str | None = None,
) -> str:
    """Generate a unique key for a confirmation request."""
    import hashlib
    import json

    args_str = json.dumps(arguments, sort_keys=True, default=str)
    args_hash = hashlib.sha256(args_str.encode()).hexdigest()[:12]
    ctx = context_id or "default"
    return f"{ctx}:{tool_name}:{args_hash}"
