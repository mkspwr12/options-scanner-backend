"""Tests for the rate limiting middleware."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient


class TestRateLimitMiddleware:
    """Unit tests for the sliding-window rate limiter."""

    def _make_app(self, max_requests: int = 5, window_seconds: int = 60) -> FastAPI:
        from app.middleware.rate_limit import RateLimitMiddleware

        test_app = FastAPI()
        test_app.add_middleware(
            RateLimitMiddleware,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        @test_app.get("/test")
        def _() -> dict:
            return {"ok": True}

        return test_app

    def test_allows_under_limit(self) -> None:
        app = self._make_app(max_requests=5)
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_blocks_over_limit(self) -> None:
        app = self._make_app(max_requests=3)
        client = TestClient(app)
        for _ in range(3):
            client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429

    def test_429_includes_retry_after(self) -> None:
        app = self._make_app(max_requests=1)
        client = TestClient(app)
        client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_429_json_format(self) -> None:
        app = self._make_app(max_requests=1)
        client = TestClient(app)
        client.get("/test")
        resp = client.get("/test")
        data = resp.json()
        assert data["status"] == "error"
        assert data["code"] == 429

    def test_disabled_when_zero(self) -> None:
        app = self._make_app(max_requests=0)
        client = TestClient(app)
        # Should never block
        for _ in range(100):
            resp = client.get("/test")
            assert resp.status_code == 200
