"""Options chain router — fetch live options data with Greek enrichment."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from ..dependencies import get_options_chain_service
from ..services.options_chain_service import OptionsChainService

router = APIRouter(prefix="/api", tags=["Options Chain"])


@router.get("/options-chain/{ticker}")
def get_options_chain(
    ticker: str,
    response: Response,
    expiration: str | None = Query(
        default=None, description="Expiration date YYYY-MM-DD"
    ),
    svc: OptionsChainService = Depends(get_options_chain_service),
) -> dict:
    """Fetch the options chain for a ticker symbol.

    Returns contracts enriched with computed Greeks, DTE,
    and moneyness classification.
    """
    result = svc.get_chain(ticker.upper(), expiration)
    _inject_rate_limit_headers(response, svc, result.get("provider"))
    return result


@router.get("/options-chain/{ticker}/expirations")
def get_expirations(
    ticker: str,
    response: Response,
    svc: OptionsChainService = Depends(get_options_chain_service),
) -> dict:
    """Return available expiration dates for a ticker."""
    result = svc.get_expirations(ticker.upper())
    _inject_rate_limit_headers(response, svc, result.get("provider"))
    return result


def _inject_rate_limit_headers(
    response: Response, svc: OptionsChainService, provider_id: str | None
) -> None:
    """Set X-RateLimit-* and X-Provider-* response headers."""
    if provider_id and svc._registry is not None:
        info = svc._registry.get_rate_limit_info(provider_id)
        if info:
            response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
            response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
            response.headers["X-RateLimit-Window"] = info.get("window", "hour")

            # Retry-After when rate limited
            if info.get("remaining", 1) <= 0:
                response.headers["Retry-After"] = str(info.get("reset", 3600))

        response.headers["X-Provider-ID"] = provider_id

        # Determine provider status
        entry = svc._registry.get_entry(provider_id)
        if entry:
            if not entry.circuit_breaker.allow_request():
                status = "degraded"
            elif svc._registry.is_rate_limited(provider_id):
                status = "rate-limited"
            else:
                status = "connected"
        else:
            status = "unknown"
        response.headers["X-Provider-Status"] = status
