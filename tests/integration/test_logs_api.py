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

    def test_returns_list_of_entries(self, client: TestClient) -> None:
        resp = client.get("/api/logs")
        assert isinstance(resp.json()["logs"], list)

    def test_total_is_integer(self, client: TestClient) -> None:
        resp = client.get("/api/logs")
        assert isinstance(resp.json()["total"], int)

    def test_limit_parameter(self, client: TestClient) -> None:
        resp = client.get("/api/logs?limit=5")
        assert resp.status_code == 200


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

    def test_post_log_default_level_info(self, client: TestClient) -> None:
        resp = client.post("/api/logs", json={"message": "uses default level"})
        assert resp.status_code == 200

    def test_post_debug_level(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={"level": "debug", "message": "debug msg"},
        )
        assert resp.status_code == 200

    def test_post_warning_level(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={"level": "warning", "message": "warn msg"},
        )
        assert resp.status_code == 200

    def test_post_error_level(self, client: TestClient) -> None:
        resp = client.post(
            "/api/logs",
            json={"level": "error", "message": "error msg"},
        )
        assert resp.status_code == 200

    def test_post_empty_body_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/logs", json={})
        assert resp.status_code == 422

    def test_log_persists_and_retrievable(self, client: TestClient) -> None:
        """A posted log should appear in subsequent GET."""
        unique_msg = "unique_integration_test_msg_12345"
        client.post(
            "/api/logs",
            json={"level": "info", "message": unique_msg},
        )
        resp = client.get("/api/logs?limit=50")
        messages = [e["message"] for e in resp.json()["logs"]]
        assert unique_msg in messages
