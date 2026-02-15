"""Integration tests for logging endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestGetLogs:
    def test_returns_logs(self, client: TestClient) -> None:
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "logs" in data
        assert "total" in data


class TestReceiveLogs:
    def test_post_log_entry(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={"level": "info", "message": "test log entry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["logged"] is True

    def test_post_log_with_data(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={
                "level": "error",
                "message": "something broke",
                "data": {"key": "value"},
            },
        )
        assert resp.status_code == 200

    def test_post_log_invalid_level_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={"level": "critical", "message": "invalid level"},
        )
        assert resp.status_code == 422

    def test_post_log_missing_message_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/logs", json={"level": "info"})
        assert resp.status_code == 422
