"""Logging router."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from ..schemas import LogEntryRequest

router = APIRouter(prefix="/api", tags=["Logs"])


def _get_log_store() -> Any:
    """Lazy import to avoid circular dependency."""
    from ..main import log_store
    return log_store


@router.get("/logs")
def get_logs(limit: int = 100) -> dict:
    """Get recent backend logs for debugging."""
    store = _get_log_store()
    return {
        "status": "ok",
        "logs": store.get_logs(limit),
        "total": len(store.logs),
    }


@router.post("/logs")
def receive_logs(log_entry: LogEntryRequest) -> dict:
    """Receive logs from frontend and store them."""
    store = _get_log_store()
    store.add(log_entry.level, log_entry.message, log_entry.data)
    return {"status": "ok", "logged": True}
