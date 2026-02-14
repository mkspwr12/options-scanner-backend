from __future__ import annotations

import pyodbc
from azure.identity import DefaultAzureCredential

from .config import get_settings

SQL_COPT_SS_ACCESS_TOKEN = 1256


def _normalize_connection_string(raw: str, driver: str) -> str:
    parts: dict[str, str] = {}
    for item in raw.split(";"):
        if not item.strip() or "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    # Remove auth-related fields that conflict with token auth
    for key in ("authentication", "user id", "uid", "password", "pwd"):
        parts.pop(key, None)

    if "driver" not in parts:
        parts["driver"] = f"{{{driver}}}"

    if "encrypt" not in parts:
        parts["encrypt"] = "yes"

    if "trustservercertificate" not in parts:
        parts["trustservercertificate"] = "no"

    return ";".join(f"{key}={value}" for key, value in parts.items()) + ";"


def get_connection() -> pyodbc.Connection:
    settings = get_settings()
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id)
    token = credential.get_token("https://database.windows.net//.default").token
    token_bytes = token.encode("utf-16-le")
    conn_str = _normalize_connection_string(settings.sql_connection_string, settings.sql_driver)

    return pyodbc.connect(
        conn_str,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_bytes},
        timeout=30,
    )
