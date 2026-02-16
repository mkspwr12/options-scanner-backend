from __future__ import annotations

from dataclasses import dataclass, field
import os


def _parse_origins(raw: str) -> list[str]:
    """Parse comma-separated CORS origins, stripping whitespace."""
    return [o.strip() for o in raw.split(",") if o.strip()]


_DEFAULT_ORIGINS = [
    "https://options-scanner-frontend-2exk6s.azurewebsites.net",
    "http://localhost:3000",
]


@dataclass(frozen=True)
class Settings:
    sql_connection_string: str
    azure_client_id: str | None
    sql_driver: str
    allowed_origins: list[str] = field(default_factory=list)
    api_key: str | None = None
    scan_interval_minutes: int = 15
    scan_enabled: bool = True
    log_retention: int = 1000
    market_data_provider: str = "mock"
    rate_limit_per_minute: int = 60
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout: int = 300
    encryption_key: str | None = None


def get_settings() -> Settings:
    sql_connection_string = os.getenv("SQL_CONNECTION_STRING", "").strip()
    if not sql_connection_string:
        raise RuntimeError("SQL_CONNECTION_STRING is required")

    azure_client_id = os.getenv("AZURE_CLIENT_ID")
    sql_driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()

    raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
    allowed_origins = _parse_origins(raw_origins) if raw_origins else _DEFAULT_ORIGINS

    api_key = os.getenv("API_KEY")

    scan_interval = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    scan_enabled = os.getenv("SCAN_ENABLED", "true").lower() in ("true", "1", "yes")
    log_retention = int(os.getenv("LOG_RETENTION", "1000"))
    market_data_provider = os.getenv("MARKET_DATA_PROVIDER", "mock").strip().lower()
    rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    circuit_breaker_threshold = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
    circuit_breaker_timeout = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))
    encryption_key = os.getenv("ENCRYPTION_KEY")

    return Settings(
        sql_connection_string=sql_connection_string,
        azure_client_id=azure_client_id,
        sql_driver=sql_driver,
        allowed_origins=allowed_origins,
        api_key=api_key,
        scan_interval_minutes=scan_interval,
        scan_enabled=scan_enabled,
        log_retention=log_retention,
        market_data_provider=market_data_provider,
        rate_limit_per_minute=rate_limit_per_minute,
        circuit_breaker_threshold=circuit_breaker_threshold,
        circuit_breaker_timeout=circuit_breaker_timeout,
        encryption_key=encryption_key,
    )
