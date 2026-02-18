"""Integration tests for POST /api/portfolio/add-position and GET /api/portfolio/positions (Issue #18)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _valid_position_payload(**overrides) -> dict:
    base = {
        "symbol": "NVDA",
        "strike": 200.0,
        "expiration": "2025-07-18",
        "type": "call",
        "quantity": 2,
        "premium": 8.50,
        "entryDate": "2025-01-20",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /api/portfolio/add-position
# ---------------------------------------------------------------------------


class TestAddPositionEndpoint:
    """Integration tests for the add-position endpoint."""

    def test_add_position_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        assert resp.status_code == 201

    def test_add_position_returns_success(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        data = resp.json()
        assert data["success"] is True
        assert "position" in data

    def test_position_has_id(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        data = resp.json()
        assert "id" in data["position"]
        assert data["position"]["id"].startswith("pos-")

    def test_position_has_correct_fields(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        pos = resp.json()["position"]
        assert pos["symbol"] == "NVDA"
        assert pos["strike"] == 200.0
        assert pos["expiration"] == "2025-07-18"
        assert pos["type"] == "call"
        assert pos["quantity"] == 2
        assert pos["premium"] == 8.50

    def test_position_current_value_calculated(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        pos = resp.json()["position"]
        # currentValue = premium * quantity * 100 = 8.50 * 2 * 100 = 1700.0
        assert pos["currentValue"] == 1700.0

    def test_position_pnl_starts_at_zero(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json=_valid_position_payload())
        pos = resp.json()["position"]
        assert pos["pnl"] == 0

    def test_symbol_uppercased(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(symbol="nvda"),
        )
        assert resp.status_code == 201
        assert resp.json()["position"]["symbol"] == "NVDA"

    def test_type_lowercased(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(type="PUT"),
        )
        assert resp.status_code == 201
        assert resp.json()["position"]["type"] == "put"

    def test_missing_symbol_returns_422(self, client: TestClient) -> None:
        payload = _valid_position_payload()
        del payload["symbol"]
        resp = client.post("/api/portfolio/add-position", json=payload)
        assert resp.status_code == 422

    def test_empty_symbol_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(symbol=""),
        )
        assert resp.status_code == 422

    def test_invalid_expiration_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(expiration="07/18/2025"),
        )
        assert resp.status_code == 422

    def test_invalid_entry_date_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(entryDate="Jan 20 2025"),
        )
        assert resp.status_code == 422

    def test_negative_strike_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(strike=-50.0),
        )
        assert resp.status_code == 422

    def test_zero_premium_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(premium=0),
        )
        assert resp.status_code == 422

    def test_zero_quantity_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(quantity=0),
        )
        assert resp.status_code == 422

    def test_invalid_type_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/add-position",
            json=_valid_position_payload(type="straddle"),
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/add-position", json={})
        assert resp.status_code == 422

    def test_entry_date_omitted_uses_default(self, client: TestClient) -> None:
        payload = _valid_position_payload()
        del payload["entryDate"]
        resp = client.post("/api/portfolio/add-position", json=payload)
        assert resp.status_code == 201
        # entryDate should be filled in with today's date
        entry = resp.json()["position"]["entryDate"]
        assert len(entry) == 10  # YYYY-MM-DD

    def test_quantity_defaults_to_one(self, client: TestClient) -> None:
        payload = _valid_position_payload()
        del payload["quantity"]
        resp = client.post("/api/portfolio/add-position", json=payload)
        assert resp.status_code == 201
        assert resp.json()["position"]["quantity"] == 1


# ---------------------------------------------------------------------------
# GET /api/portfolio/positions
# ---------------------------------------------------------------------------


class TestListPositionsEndpoint:
    """Integration tests for the list-positions endpoint."""

    def test_list_positions_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/positions")
        assert resp.status_code == 200

    def test_list_positions_has_status_ok(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/positions")
        data = resp.json()
        assert data["status"] == "ok"
        assert "positions" in data
        assert "count" in data

    def test_list_positions_empty_initially(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/positions")
        data = resp.json()
        assert data["positions"] == []
        assert data["count"] == 0
