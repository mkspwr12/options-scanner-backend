"""Tests for the API key authentication middleware."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestApiKeyAuth:
    """Test API key auth middleware behaviour."""

    def test_no_api_key_configured_allows_all(self) -> None:
        """When API_KEY is not set, all requests pass through."""
        # Default test env has no API_KEY
        client = TestClient(app)
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_no_api_key_api_routes_accessible(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/logs")
        assert resp.status_code == 200


class TestApiKeyAuthEnabled:
    """Test with API key explicitly configured."""

    def setup_method(self) -> None:
        os.environ["API_KEY"] = "test-secret-key-123"
        # Force reimport to pick up new middleware config
        # We'll use a fresh app with middleware
        from app.middleware.auth import ApiKeyMiddleware
        self._middleware = ApiKeyMiddleware

    def teardown_method(self) -> None:
        os.environ.pop("API_KEY", None)

    def test_middleware_rejects_missing_key(self) -> None:
        from app.middleware.auth import ApiKeyMiddleware
        from fastapi import FastAPI
        from starlette.testclient import TestClient as STC

        test_app = FastAPI()
        test_app.add_middleware(ApiKeyMiddleware, api_key="my-key")

        @test_app.get("/api/test")
        def _() -> dict:
            return {"ok": True}

        client = STC(test_app)
        resp = client.get("/api/test")
        assert resp.status_code == 401
        assert resp.json()["status"] == "error"

    def test_middleware_accepts_correct_key(self) -> None:
        from app.middleware.auth import ApiKeyMiddleware
        from fastapi import FastAPI
        from starlette.testclient import TestClient as STC

        test_app = FastAPI()
        test_app.add_middleware(ApiKeyMiddleware, api_key="my-key")

        @test_app.get("/api/test")
        def _() -> dict:
            return {"ok": True}

        client = STC(test_app)
        resp = client.get("/api/test", headers={"X-API-Key": "my-key"})
        assert resp.status_code == 200

    def test_middleware_allows_public_paths(self) -> None:
        from app.middleware.auth import ApiKeyMiddleware
        from fastapi import FastAPI
        from starlette.testclient import TestClient as STC

        test_app = FastAPI()
        test_app.add_middleware(ApiKeyMiddleware, api_key="my-key")

        @test_app.get("/healthz")
        def _() -> dict:
            return {"status": "ok"}

        client = STC(test_app)
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_middleware_rejects_wrong_key(self) -> None:
        from app.middleware.auth import ApiKeyMiddleware
        from fastapi import FastAPI
        from starlette.testclient import TestClient as STC

        test_app = FastAPI()
        test_app.add_middleware(ApiKeyMiddleware, api_key="correct-key")

        @test_app.get("/api/test")
        def _() -> dict:
            return {"ok": True}

        client = STC(test_app)
        resp = client.get("/api/test", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401
