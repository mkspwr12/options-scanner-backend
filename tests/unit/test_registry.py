"""Unit tests for the ProviderRegistry."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.providers.registry import ProviderRegistry
from app.exceptions import NotFoundError, ProviderError


class TestProviderRegistry:
    def setup_method(self) -> None:
        self.registry = ProviderRegistry()

    def test_register_mock_provider(self) -> None:
        self.registry.register("test-1", {"type": "MASSIVE", "enabled": True, "priority": 1})
        pid, provider = self.registry.get_best_provider()
        assert pid == "test-1"
        assert provider is not None

    def test_register_unknown_type_still_registers(self) -> None:
        """Unknown types register but their provider instance is None."""
        self.registry.register("test-2", {"type": "UNKNOWN", "enabled": True, "priority": 1})
        entry = self.registry.get_entry("test-2")
        assert entry is not None
        assert entry.provider is None

    def test_get_best_provider_priority_order(self) -> None:
        self.registry.register("low", {"type": "MASSIVE", "enabled": True, "priority": 10})
        self.registry.register("high", {"type": "MASSIVE", "enabled": True, "priority": 1})
        pid, _ = self.registry.get_best_provider()
        assert pid == "high"

    def test_get_best_provider_skips_disabled(self) -> None:
        self.registry.register("disabled", {"type": "MASSIVE", "enabled": False, "priority": 1})
        self.registry.register("active", {"type": "MASSIVE", "enabled": True, "priority": 2})
        pid, _ = self.registry.get_best_provider()
        assert pid == "active"

    def test_get_best_provider_no_providers_raises(self) -> None:
        with pytest.raises(ProviderError, match="No providers available"):
            self.registry.get_best_provider()

    def test_unregister(self) -> None:
        self.registry.register("removeme", {"type": "MASSIVE", "enabled": True, "priority": 1})
        self.registry.unregister("removeme")
        with pytest.raises(ProviderError):
            self.registry.get_best_provider()

    def test_record_success(self) -> None:
        self.registry.register("p1", {"type": "MASSIVE", "enabled": True, "priority": 1})
        self.registry.record_success("p1")  # should not raise

    def test_record_failure(self) -> None:
        self.registry.register("p1", {"type": "MASSIVE", "enabled": True, "priority": 1})
        self.registry.record_failure("p1")  # should not raise

    def test_get_rate_limit_info(self) -> None:
        self.registry.register(
            "p1",
            {"type": "MASSIVE", "enabled": True, "priority": 1, "rate_limit_max_per_hour": 100},
        )
        self.registry.record_call("p1")
        info = self.registry.get_rate_limit_info("p1")
        assert info["limit"] == 100
        assert info["remaining"] == 99

    def test_get_provider_not_found(self) -> None:
        prov = self.registry.get_provider("nonexistent")
        assert prov is None

    def test_clear(self) -> None:
        self.registry.register("a", {"type": "MASSIVE", "enabled": True, "priority": 1})
        self.registry.clear()
        with pytest.raises(ProviderError):
            self.registry.get_best_provider()
