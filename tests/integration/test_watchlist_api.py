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

    def test_symbols_are_strings(self, client: TestClient) -> None:
        resp = client.get("/api/watchlist")
        for symbol in resp.json()["symbols"]:
            assert isinstance(symbol, str)
            assert len(symbol) > 0


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

    def test_add_empty_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={"symbol": ""})
        assert resp.status_code == 422

    def test_add_returns_message(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={"symbol": "AMZN"})
        data = resp.json()
        assert "message" in data
        assert "AMZN" in data["message"]

    def test_add_whitespace_symbol_stripped(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/add", json={"symbol": "  nvda  "})
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "NVDA"


class TestRemoveFromWatchlist:
    def test_remove_symbol(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={"symbol": "META"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_remove_missing_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={})
        assert resp.status_code == 422

    def test_remove_empty_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={"symbol": ""})
        assert resp.status_code == 422

    def test_remove_returns_message(self, client: TestClient) -> None:
        resp = client.post("/api/watchlist/remove", json={"symbol": "SPY"})
        data = resp.json()
        assert "message" in data
        assert "SPY" in data["message"]
