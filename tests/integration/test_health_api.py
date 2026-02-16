"""Integration tests for health and diagnostics endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthz:
    def test_healthz_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_healthz_no_db_dependency(self, client: TestClient) -> None:
        """Healthz should always work even without DB."""
        resp = client.get("/healthz")
        assert resp.status_code == 200


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["auth"] == "managed-identity"

    def test_health_includes_timestamp(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format

    def test_health_includes_database_info(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "database" in data
        assert data["database"] == "configured"


class TestRoot:
    def test_root_returns_api_info(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Options Scanner API"
        assert "endpoints" in data

    def test_root_lists_all_endpoints(self, client: TestClient) -> None:
        resp = client.get("/")
        endpoints = resp.json()["endpoints"]
        expected_paths = [
            "GET /health",
            "GET /healthz",
            "GET /api/scan",
            "GET /api/portfolio",
            "GET /api/watchlist",
            "POST /api/trades/track",
            "POST /api/trades/close",
            "GET /api/multi-leg-opportunities",
            "GET /api/logs",
            "POST /api/logs",
        ]
        for path in expected_paths:
            assert path in endpoints, f"Missing endpoint: {path}"

    def test_root_version(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.json()["version"] == "3.0.0"


class TestDebugConfig:
    def test_debug_config_returns_settings(self, client: TestClient) -> None:
        resp = client.get("/api/debug/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "sql_driver" in data
        assert "sql_connection_string_set" in data
        assert "timestamp" in data

    def test_debug_config_does_not_expose_secrets(self, client: TestClient) -> None:
        resp = client.get("/api/debug/config")
        data = resp.json()
        # Should not contain the actual connection string or API key
        assert "sql_connection_string" not in data
        assert "api_key" not in data
        # Only boolean flags
        assert isinstance(data["sql_connection_string_set"], bool)

    def test_debug_config_scan_settings(self, client: TestClient) -> None:
        resp = client.get("/api/debug/config")
        data = resp.json()
        assert "scan_enabled" in data
        assert "scan_interval_minutes" in data
        assert "market_data_provider" in data

    def test_debug_config_allowed_origins(self, client: TestClient) -> None:
        resp = client.get("/api/debug/config")
        data = resp.json()
        assert "allowed_origins" in data
        assert isinstance(data["allowed_origins"], list)


class TestDiagnostics:
    def test_diagnostics_endpoint_exists(self, client: TestClient) -> None:
        resp = client.get("/api/diagnostics")
        # May be 200 or 503 depending on DB, but should not 404
        assert resp.status_code in (200, 503)

    def test_diagnostics_returns_backend_info(self, client: TestClient) -> None:
        resp = client.get("/api/diagnostics")
        if resp.status_code == 200:
            data = resp.json()
            assert data["backend"]["version"] == "3.0.0"
            assert "database" in data
            assert "environment" in data
