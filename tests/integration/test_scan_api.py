"""Integration tests for scan endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestScan:
    def test_scan_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "opportunities" in data
        assert len(data["opportunities"]) >= 1

    def test_scan_with_filters(self, client: TestClient) -> None:
        resp = client.get("/api/scan?symbol=META&optionType=CALL&minConfidence=70")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_scan_limit_parameter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=1")
        assert resp.status_code == 200

    def test_scan_invalid_limit(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=0")
        assert resp.status_code == 422

    def test_scan_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=999")
        assert resp.status_code == 422


class TestMultiLegOpportunities:
    def test_returns_strategies(self, client: TestClient) -> None:
        resp = client.get("/api/multi-leg-opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["opportunities"]) >= 1
