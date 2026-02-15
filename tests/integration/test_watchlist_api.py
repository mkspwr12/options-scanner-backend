"""Integration tests for watchlist endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestGetWatchlist:
    def test_returns_symbols(self, client: TestClient) -> None:
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["symbols"], list)


class TestAddToWatchlist:
    def test_add_symbol(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={"symbol": "TSLA"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["symbol"] == "TSLA"

    def test_add_lowercased_symbol(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={"symbol": "goog"})
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "GOOG"

    def test_add_missing_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={})
        assert resp.status_code == 422


class TestRemoveFromWatchlist:
    def test_remove_symbol(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={"symbol": "META"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_remove_missing_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={})
        assert resp.status_code == 422
