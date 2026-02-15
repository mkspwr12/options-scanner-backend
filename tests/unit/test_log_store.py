"""Unit tests for LogStore and safe_log in app/main.py.

Covers:
- LogStore ring-buffer behaviour (add, get_logs, overflow)
- safe_log() dual-write to store + logger
- Fallback behaviour on errors
"""
from __future__ import annotations

import logging
import os

os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")

from app.main import LogStore, safe_log, log_store


class TestLogStore:
    def test_add_and_retrieve(self) -> None:
        store = LogStore(max_entries=10)
        store.add("info", "test message")
        logs = store.get_logs(10)
        assert len(logs) == 1
        assert logs[0]["message"] == "test message"
        assert logs[0]["level"] == "info"
        assert logs[0]["source"] == "backend"

    def test_timestamp_present(self) -> None:
        store = LogStore()
        store.add("error", "oops")
        entry = store.get_logs(1)[0]
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]  # ISO format

    def test_data_stored(self) -> None:
        store = LogStore()
        store.add("warning", "alert", {"key": "value"})
        entry = store.get_logs(1)[0]
        assert entry["data"] == {"key": "value"}

    def test_data_defaults_to_none(self) -> None:
        store = LogStore()
        store.add("info", "no data")
        entry = store.get_logs(1)[0]
        assert entry["data"] is None

    def test_ring_buffer_overflow(self) -> None:
        store = LogStore(max_entries=3)
        store.add("info", "msg-1")
        store.add("info", "msg-2")
        store.add("info", "msg-3")
        store.add("info", "msg-4")  # should evict msg-1

        assert len(store.logs) == 3
        messages = [e["message"] for e in store.logs]
        assert "msg-1" not in messages
        assert "msg-4" in messages

    def test_get_logs_returns_most_recent_first(self) -> None:
        store = LogStore()
        store.add("info", "first")
        store.add("info", "second")
        store.add("info", "third")
        logs = store.get_logs(10)
        assert logs[0]["message"] == "third"
        assert logs[-1]["message"] == "first"

    def test_get_logs_respects_limit(self) -> None:
        store = LogStore()
        for i in range(20):
            store.add("info", f"msg-{i}")
        logs = store.get_logs(5)
        assert len(logs) == 5
        # Most recent should be first
        assert logs[0]["message"] == "msg-19"

    def test_get_logs_empty_store(self) -> None:
        store = LogStore()
        assert store.get_logs(100) == []

    def test_custom_max_entries(self) -> None:
        store = LogStore(max_entries=5)
        assert store.max_entries == 5

    def test_default_max_entries(self) -> None:
        store = LogStore()
        assert store.max_entries == 1000


class TestSafeLog:
    """Tests for the safe_log() function."""

    def test_adds_to_global_log_store(self) -> None:
        initial_count = len(log_store.logs)
        safe_log("info", "safe log test")
        assert len(log_store.logs) >= initial_count + 1

    def test_with_data(self) -> None:
        safe_log("warning", "test with data", {"detail": 42})
        # Should not raise

    def test_invalid_level_no_crash(self) -> None:
        # safe_log uses getattr with fallback — shouldn't crash on unknown levels
        safe_log("nonexistent_level", "should not crash")
