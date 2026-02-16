"""Provider repository — SQL data access for the providers table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection
from ..exceptions import ConflictError, DatabaseError, NotFoundError

logger = logging.getLogger(__name__)


class ProviderRepository:
    """Encapsulates all SQL operations on the ``providers`` table."""

    def get_all(self) -> list[dict[str, Any]]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM providers ORDER BY priority ASC")
                cols = [col[0] for col in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list providers")
            raise DatabaseError(f"Failed to list providers: {exc}") from exc

    def get_by_id(self, provider_id: str) -> dict[str, Any]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
                row = cursor.fetchone()
                if row is None:
                    raise NotFoundError("Provider", provider_id)
                cols = [col[0] for col in cursor.description]
                return dict(zip(cols, row))
        except NotFoundError:
            raise
        except Exception as exc:
            logger.exception("Failed to get provider %s", provider_id)
            raise DatabaseError(f"Failed to get provider: {exc}") from exc

    def insert(self, data: dict[str, Any]) -> str:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Check name uniqueness
                cursor.execute(
                    "SELECT COUNT(*) FROM providers WHERE name = ?", (data["name"],)
                )
                if cursor.fetchone()[0] > 0:
                    raise ConflictError(f"Provider with name '{data['name']}' already exists")

                cursor.execute(
                    """
                    INSERT INTO providers
                        (id, name, type, api_key_encrypted, api_secret_encrypted,
                         base_url, enabled, priority,
                         rate_limit_max_per_hour, rate_limit_max_per_day,
                         rate_limit_cost_per_call)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["id"],
                        data["name"],
                        data["type"],
                        data.get("api_key_encrypted"),
                        data.get("api_secret_encrypted"),
                        data["base_url"],
                        data.get("enabled", True),
                        data["priority"],
                        data.get("rate_limit_max_per_hour", 2000),
                        data.get("rate_limit_max_per_day", 20000),
                        data.get("rate_limit_cost_per_call", 0),
                    ),
                )
                conn.commit()
            return data["id"]
        except (ConflictError, NotFoundError):
            raise
        except Exception as exc:
            logger.exception("Failed to insert provider")
            raise DatabaseError(f"Failed to insert provider: {exc}") from exc

    def update(self, provider_id: str, data: dict[str, Any]) -> dict[str, Any]:
        # Verify exists first
        self.get_by_id(provider_id)
        sets: list[str] = []
        params: list[Any] = []
        field_map = {
            "name": "name",
            "enabled": "enabled",
            "priority": "priority",
            "base_url": "base_url",
            "api_key_encrypted": "api_key_encrypted",
            "api_secret_encrypted": "api_secret_encrypted",
            "rate_limit_max_per_hour": "rate_limit_max_per_hour",
            "rate_limit_max_per_day": "rate_limit_max_per_day",
            "rate_limit_cost_per_call": "rate_limit_cost_per_call",
        }
        for key, col in field_map.items():
            if key in data:
                sets.append(f"{col} = ?")
                params.append(data[key])

        if not sets:
            return self.get_by_id(provider_id)

        sets.append("updated_at = GETUTCDATE()")
        params.append(provider_id)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE providers SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
                conn.commit()
            return self.get_by_id(provider_id)
        except Exception as exc:
            logger.exception("Failed to update provider %s", provider_id)
            raise DatabaseError(f"Failed to update provider: {exc}") from exc

    def delete(self, provider_id: str) -> None:
        self.get_by_id(provider_id)  # raises NotFoundError if missing
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Prevent deleting the last provider
                cursor.execute("SELECT COUNT(*) FROM providers")
                if cursor.fetchone()[0] <= 1:
                    raise ConflictError("Cannot delete the last remaining provider")
                cursor.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
                conn.commit()
        except ConflictError:
            raise
        except Exception as exc:
            logger.exception("Failed to delete provider %s", provider_id)
            raise DatabaseError(f"Failed to delete provider: {exc}") from exc

    def count(self) -> int:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM providers")
                return cursor.fetchone()[0]
        except Exception:
            return 0
