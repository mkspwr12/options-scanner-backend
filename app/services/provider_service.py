"""Provider management service — CRUD, connection testing, encryption."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from ..exceptions import NotFoundError, ProviderError
from ..models import ConnectionTestResult, ProviderConfig, RateLimitConfig
from ..providers.encryption import decrypt, encrypt, mask_key
from ..providers.registry import ProviderRegistry
from ..repositories.provider_repository import ProviderRepository

logger = logging.getLogger(__name__)

_VALID_TYPES = {"MASSIVE", "ALPACA", "TRADIER", "CUSTOM"}


class ProviderService:
    """Business logic for provider CRUD and connection testing."""

    def __init__(
        self,
        repo: ProviderRepository | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self._repo = repo if repo is not None else ProviderRepository()
        self._registry = registry if registry is not None else ProviderRegistry()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_providers(self) -> list[ProviderConfig]:
        rows = self._repo.get_all()
        return [self._row_to_config(r) for r in rows]

    def get_provider(self, provider_id: str) -> ProviderConfig:
        row = self._repo.get_by_id(provider_id)
        if row is None:
            raise NotFoundError("Provider", provider_id)
        return self._row_to_config(row)

    def create_provider(self, data: dict[str, Any]) -> ProviderConfig:
        provider_type = data.get("type", "").upper()
        if provider_type not in _VALID_TYPES:
            raise ProviderError(
                f"Invalid provider type: {provider_type}. "
                f"Must be one of {sorted(_VALID_TYPES)}"
            )

        provider_id = f"prov-{uuid.uuid4().hex[:12]}"

        api_key_enc = encrypt(data["apiKey"]) if data.get("apiKey") else None
        api_secret_enc = encrypt(data["apiSecret"]) if data.get("apiSecret") else None

        rate_limit = data.get("rateLimit") or {}

        row = {
            "id": provider_id,
            "name": data["name"],
            "type": provider_type,
            "api_key_encrypted": api_key_enc,
            "api_secret_encrypted": api_secret_enc,
            "base_url": data.get("baseUrl", ""),
            "enabled": True,
            "priority": data.get("priority", 1),
            "rate_limit_max_per_hour": rate_limit.get("maxPerHour", 2000),
            "rate_limit_max_per_day": rate_limit.get("maxPerDay", 20000),
            "rate_limit_cost_per_call": rate_limit.get("costPerCall", 0.0),
        }

        self._repo.insert(row)
        self._registry.register(provider_id, row)
        return self.get_provider(provider_id)

    def update_provider(self, provider_id: str, data: dict[str, Any]) -> ProviderConfig:
        existing = self._repo.get_by_id(provider_id)
        if existing is None:
            raise NotFoundError("Provider", provider_id)

        updates: dict[str, Any] = {}
        if "name" in data and data["name"] is not None:
            updates["name"] = data["name"]
        if "enabled" in data and data["enabled"] is not None:
            updates["enabled"] = 1 if data["enabled"] else 0
        if "priority" in data and data["priority"] is not None:
            updates["priority"] = data["priority"]
        if "baseUrl" in data and data["baseUrl"] is not None:
            updates["base_url"] = data["baseUrl"]
        if data.get("apiKey"):
            updates["api_key_encrypted"] = encrypt(data["apiKey"])
        if data.get("apiSecret"):
            updates["api_secret_encrypted"] = encrypt(data["apiSecret"])
        if data.get("rateLimit"):
            rl = data["rateLimit"]
            if "maxPerHour" in rl:
                updates["rate_limit_max_per_hour"] = rl["maxPerHour"]
            if "maxPerDay" in rl:
                updates["rate_limit_max_per_day"] = rl["maxPerDay"]
            if "costPerCall" in rl:
                updates["rate_limit_cost_per_call"] = rl["costPerCall"]

        if updates:
            self._repo.update(provider_id, updates)

        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: str) -> dict[str, str]:
        existing = self._repo.get_by_id(provider_id)
        if existing is None:
            raise NotFoundError("Provider", provider_id)

        # Prevent deleting the last remaining provider
        all_providers = self._repo.get_all()
        if len(all_providers) <= 1:
            from ..exceptions import ConflictError
            raise ConflictError(
                "Cannot delete the last remaining provider. "
                "Add another provider before removing this one."
            )

        self._repo.delete(provider_id)
        self._registry.unregister(provider_id)
        return {"status": "deleted", "id": provider_id}

    # ------------------------------------------------------------------
    # Connection testing
    # ------------------------------------------------------------------

    def test_connection(
        self, provider_id: str, override: dict[str, Any] | None = None
    ) -> ConnectionTestResult:
        config = self._repo.get_by_id(provider_id)
        if config is None:
            raise NotFoundError("Provider", provider_id)

        provider_type = (override or {}).get("type", config.get("type", "")).upper()
        base_url = (override or {}).get("baseUrl", config.get("base_url", ""))

        import signal
        import threading

        start = time.monotonic()
        timeout_seconds = 10

        try:
            result_container: dict[str, Any] = {"available": False, "error": None}

            def _do_test() -> None:
                try:
                    if provider_type == "MASSIVE":
                        from ..providers.massive_provider import MassiveProvider

                        p = MassiveProvider()
                        result_container["available"] = p.is_available()
                        result_container["endpoint"] = f"{base_url or 'https://api.massive.com'}/v2/aggs/ticker/AAPL/prev"
                    elif provider_type == "ALPACA":
                        result_container["available"] = False
                        result_container["endpoint"] = f"{base_url or 'https://data.alpaca.markets'}/v2/account"
                        result_container["error"] = "ALPACA provider not yet implemented"
                    elif provider_type == "TRADIER":
                        result_container["available"] = False
                        result_container["endpoint"] = f"{base_url or 'https://api.tradier.com'}/v1/user/profile"
                        result_container["error"] = "TRADIER provider not yet implemented"
                    else:
                        result_container["available"] = False
                        result_container["endpoint"] = f"{base_url}/healthz" if base_url else None
                        result_container["error"] = f"Provider type '{provider_type}' not available"
                except Exception as exc:
                    result_container["error"] = str(exc)

            thread = threading.Thread(target=_do_test, daemon=True)
            thread.start()
            thread.join(timeout=timeout_seconds)

            latency_ms = int((time.monotonic() - start) * 1000)

            if thread.is_alive():
                return ConnectionTestResult(
                    success=False,
                    latencyMs=timeout_seconds * 1000,
                    error=f"Connection timeout after {timeout_seconds} seconds",
                    details={"endpoint": result_container.get("endpoint"), "httpStatus": None, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                )

            if result_container["error"]:
                return ConnectionTestResult(
                    success=False,
                    latencyMs=latency_ms,
                    error=result_container["error"],
                    details={"endpoint": result_container.get("endpoint"), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                )

            if result_container["available"]:
                return ConnectionTestResult(
                    success=True,
                    latencyMs=latency_ms,
                    message="Connection successful",
                    details={"endpoint": result_container.get("endpoint"), "httpStatus": 200, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                )
            return ConnectionTestResult(
                success=False,
                latencyMs=latency_ms,
                error=f"Provider type '{provider_type}' not available",
                details={"endpoint": result_container.get("endpoint"), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                latencyMs=latency_ms,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_config(row: dict[str, Any]) -> ProviderConfig:
        api_key_masked = None
        if row.get("api_key_encrypted"):
            try:
                decrypted = decrypt(row["api_key_encrypted"])
                api_key_masked = mask_key(decrypted)
            except Exception:
                api_key_masked = "****"

        return ProviderConfig(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            apiKeyMasked=api_key_masked,
            baseUrl=row.get("base_url", ""),
            enabled=bool(row.get("enabled", True)),
            priority=int(row.get("priority", 1)),
            rateLimit=RateLimitConfig(
                maxPerHour=int(row.get("rate_limit_max_per_hour") or 2000),
                maxPerDay=int(row.get("rate_limit_max_per_day") or 20000),
                costPerCall=float(row.get("rate_limit_cost_per_call") or 0),
            ),
            createdAt=str(row.get("created_at", "")),
            updatedAt=str(row.get("updated_at", "")),
        )
