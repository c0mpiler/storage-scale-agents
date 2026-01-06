"""Tests for confirmation handling."""

import contextlib
from datetime import datetime, timedelta

import pytest

from scale_agents.config.settings import Settings
from scale_agents.core.exceptions import ConfirmationRequiredError
from scale_agents.tools.confirmable import (
    ConfirmationState,
    ConfirmationStatus,
    check_confirmation,
    clear_pending_confirmations,
    process_confirmation,
    requires_confirmation,
)


class TestConfirmationState:
    """Tests for ConfirmationState class."""

    def test_initial_status_is_pending(self):
        """New confirmation should be pending."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={"filesystem": "gpfs01"},
            risk_level="HIGH",
        )
        assert state.status == ConfirmationStatus.PENDING

    def test_is_expired_false_when_new(self):
        """New confirmation should not be expired."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={},
            risk_level="HIGH",
        )
        assert state.is_expired() is False

    def test_is_expired_true_when_old(self):
        """Old confirmation should be expired."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={},
            risk_level="HIGH",
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        assert state.is_expired() is True

    def test_confirm_success(self):
        """Should confirm successfully when not expired."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={},
            risk_level="HIGH",
        )
        result = state.confirm()
        assert result is True
        assert state.status == ConfirmationStatus.CONFIRMED

    def test_confirm_fails_when_expired(self):
        """Should fail to confirm when expired."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={},
            risk_level="HIGH",
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        result = state.confirm()
        assert result is False
        assert state.status == ConfirmationStatus.EXPIRED

    def test_cancel(self):
        """Should cancel successfully."""
        state = ConfirmationState(
            tool_name="delete_fileset",
            arguments={},
            risk_level="HIGH",
        )
        state.cancel()
        assert state.status == ConfirmationStatus.CANCELLED


class TestRequiresConfirmation:
    """Tests for requires_confirmation function."""

    def test_destructive_tool_requires_confirmation(self, monkeypatch):
        """Destructive tools should require confirmation."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        assert requires_confirmation("delete_fileset", {}) is True

    def test_read_only_tool_no_confirmation(self, monkeypatch):
        """Read-only tools should not require confirmation."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        assert requires_confirmation("list_filesystems", {}) is False

    def test_disabled_confirmation(self, monkeypatch):
        """Should not require confirmation when disabled."""
        # Import the module to patch its settings reference
        import scale_agents.tools.confirmable as confirmable_module
        monkeypatch.setattr(
            confirmable_module,
            "settings",
            Settings(require_confirmation=False),
        )
        assert requires_confirmation("delete_fileset", {}) is False


class TestCheckConfirmation:
    """Tests for check_confirmation function."""

    def test_raises_for_destructive_tool(self, monkeypatch):
        """Should raise ConfirmationRequiredError for destructive tools."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        clear_pending_confirmations("test_context_1")

        with pytest.raises(ConfirmationRequiredError) as exc_info:
            check_confirmation(
                "delete_fileset",
                {"filesystem": "gpfs01"},
                context_id="test_context_1",
            )

        assert exc_info.value.tool_name == "delete_fileset"
        assert exc_info.value.risk_level == "HIGH"

    def test_no_raise_for_read_only_tool(self, monkeypatch):
        """Should not raise for read-only tools."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        result = check_confirmation(
            "list_filesystems",
            {},
            context_id="test_context_2",
        )
        assert result is None

    def test_force_confirm_bypasses_check(self, monkeypatch):
        """Should bypass confirmation when force_confirm is True."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        result = check_confirmation(
            "delete_fileset",
            {"filesystem": "gpfs01"},
            context_id="test_context_3",
            force_confirm=True,
        )
        assert result is None


class TestProcessConfirmation:
    """Tests for process_confirmation function."""

    def test_confirm_with_yes(self, monkeypatch):
        """Should confirm when user says yes."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        clear_pending_confirmations("confirm_test_1")

        # Create pending confirmation
        with contextlib.suppress(ConfirmationRequiredError):
            check_confirmation(
                "delete_fileset",
                {"filesystem": "gpfs01"},
                context_id="confirm_test_1",
            )

        # Confirm
        success, message = process_confirmation("confirm_test_1", "yes")
        assert success is True
        assert "confirmed" in message.lower()

    def test_cancel_with_no(self, monkeypatch):
        """Should cancel when user says no."""
        monkeypatch.setattr(
            "scale_agents.tools.confirmable.settings",
            Settings(require_confirmation=True),
        )
        clear_pending_confirmations("confirm_test_2")

        # Create pending confirmation
        with contextlib.suppress(ConfirmationRequiredError):
            check_confirmation(
                "delete_fileset",
                {"filesystem": "gpfs01"},
                context_id="confirm_test_2",
            )

        # Cancel
        success, message = process_confirmation("confirm_test_2", "cancel")
        assert success is False
        assert "cancelled" in message.lower()

    def test_no_pending_confirmation(self):
        """Should return False when no pending confirmation exists."""
        clear_pending_confirmations("confirm_test_3")
        success, message = process_confirmation("confirm_test_3", "yes")
        assert success is False
        assert "no pending" in message.lower()
