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


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["auth"] == "managed-identity"


class TestRoot:
    def test_root_returns_api_info(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Options Scanner API"
        assert "endpoints" in data


class TestDebugConfig:
    def test_debug_config_returns_settings(self, client: TestClient) -> None:
        resp = client.get("/api/debug/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "sql_driver" in data
        assert "sql_connection_string_set" in data
        assert "timestamp" in data
