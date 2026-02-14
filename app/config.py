from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    sql_connection_string: str
    azure_client_id: str | None
    sql_driver: str


def get_settings() -> Settings:
    sql_connection_string = os.getenv("SQL_CONNECTION_STRING", "").strip()
    if not sql_connection_string:
        raise RuntimeError("SQL_CONNECTION_STRING is required")

    azure_client_id = os.getenv("AZURE_CLIENT_ID")
    sql_driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    return Settings(
        sql_connection_string=sql_connection_string,
        azure_client_id=azure_client_id,
        sql_driver=sql_driver,
    )
