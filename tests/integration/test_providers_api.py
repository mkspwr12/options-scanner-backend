"""Integration tests for the Providers API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class TestListProviders:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["providers"] == []


class TestCreateProvider:
    def test_create_valid(self, client: TestClient, mock_provider_repo: MagicMock) -> None:
        mock_provider_repo.get_by_id.return_value = {
            "id": "prov-test",
            "name": "Test Provider",
            "type": "MOCK",
            "base_url": "",
            "enabled": True,
            "priority": 1,
        }
        resp = client.post("/api/providers", json={
            "name": "Test Provider",
            "type": "MOCK",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["provider"]["name"] == "Test Provider"

    def test_create_invalid_type(self, client: TestClient) -> None:
        resp = client.post("/api/providers", json={
            "name": "Bad",
            "type": "INVALID",
        })
        # Pydantic rejects invalid Literal value with 422
        assert resp.status_code == 422

    def test_create_missing_name(self, client: TestClient) -> None:
        resp = client.post("/api/providers", json={"type": "MOCK"})
        assert resp.status_code == 422


class TestGetProvider:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/providers/nonexistent")
        assert resp.status_code == 404


class TestUpdateProvider:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.put("/api/providers/nonexistent", json={"name": "New"})
        assert resp.status_code == 404


class TestDeleteProvider:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/providers/nonexistent")
        assert resp.status_code == 404


class TestTestConnection:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/providers/nonexistent/test")
        assert resp.status_code == 404
