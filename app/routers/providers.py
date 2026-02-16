"""Provider management router — CRUD + connection testing + proxy + metrics."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Response

from ..dependencies import get_metrics_service, get_provider_service
from ..exceptions import AppError, NotFoundError, ProviderError
from ..schemas import CreateProviderRequest, ConnectionTestInput, UpdateProviderRequest
from ..services.metrics_service import MetricsService
from ..services.provider_service import ProviderService

router = APIRouter(prefix="/api/providers", tags=["Providers"])


@router.get("")
def list_providers(
    svc: ProviderService = Depends(get_provider_service),
) -> dict:
    providers = svc.list_providers()
    return {"status": "ok", "providers": [p.model_dump() for p in providers]}


@router.get("/{provider_id}")
def get_provider(
    provider_id: str,
    svc: ProviderService = Depends(get_provider_service),
) -> dict:
    provider = svc.get_provider(provider_id)
    return {"status": "ok", "provider": provider.model_dump()}


@router.post("", status_code=201)
def create_provider(
    body: CreateProviderRequest,
    svc: ProviderService = Depends(get_provider_service),
) -> dict:
    provider = svc.create_provider(body.model_dump())
    return {"status": "created", "provider": provider.model_dump()}


@router.put("/{provider_id}")
def update_provider(
    provider_id: str,
    body: UpdateProviderRequest,
    svc: ProviderService = Depends(get_provider_service),
) -> dict:
    provider = svc.update_provider(provider_id, body.model_dump(exclude_unset=True))
    return {"status": "updated", "provider": provider.model_dump()}


@router.delete("/{provider_id}", status_code=204, response_class=Response)
def delete_provider(
    provider_id: str,
    svc: ProviderService = Depends(get_provider_service),
) -> None:
    svc.delete_provider(provider_id)


@router.post("/{provider_id}/test")
def test_connection(
    provider_id: str,
    body: ConnectionTestInput | None = None,
    svc: ProviderService = Depends(get_provider_service),
) -> dict:
    override = body.model_dump(exclude_unset=True) if body else None
    result = svc.test_connection(provider_id, override)
    return {"status": "ok", "result": result.model_dump()}


# ------------------------------------------------------------------
# Provider Proxy Endpoints (Issue #4)
# ------------------------------------------------------------------


@router.get("/{provider_id}/proxy/options")
def proxy_options(
    provider_id: str,
    response: Response,
    symbol: str = Query(..., description="Ticker symbol (e.g. MSFT)"),
    expiration: str | None = Query(default=None, description="Expiration YYYY-MM-DD"),
    svc: ProviderService = Depends(get_provider_service),
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict:
    """Fetch options chain through a specific provider."""
    registry = svc._registry
    entry = registry.get_entry(provider_id)
    if entry is None:
        raise NotFoundError("Provider", provider_id)

    if not entry.config.get("enabled", True):
        raise AppError(
            f"Provider '{provider_id}' is disabled", status_code=503
        )

    if not entry.circuit_breaker.allow_request():
        raise AppError(
            f"Provider '{provider_id}' is in circuit breaker cooldown",
            status_code=503,
        )

    if registry.is_rate_limited(provider_id):
        info = registry.get_rate_limit_info(provider_id)
        raise AppError(
            f"Rate limit exceeded for provider '{provider_id}'",
            status_code=429,
        )

    provider = entry.provider
    if provider is None:
        raise AppError(
            f"Provider '{provider_id}' type not supported for proxy calls",
            status_code=502,
        )

    start = time.monotonic()
    try:
        quote = provider.get_quote(symbol.upper())
        contracts = provider.get_options_chain(symbol.upper(), expiration)
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.record_success(provider_id)
        registry.record_call(provider_id)

        # Record metrics
        metrics_svc.record(
            provider_id=provider_id,
            endpoint="/proxy/options",
            latency_ms=latency_ms,
            success=True,
        )

        # Inject rate limit headers
        _inject_provider_headers(response, registry, provider_id)

        from ..services.options_chain_service import OptionsChainService
        enriched = [OptionsChainService._enrich(c, quote.price) for c in contracts]

        expiration_dates = sorted(
            {c["expiration"] for c in enriched if c.get("expiration")}
        )

        return {
            "status": "ok",
            "ticker": symbol.upper(),
            "underlyingPrice": quote.price,
            "expirationDates": expiration_dates,
            "contracts": enriched,
            "contractCount": len(enriched),
            "provider": provider_id,
            "latencyMs": latency_ms,
        }
    except AppError:
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.record_failure(provider_id)
        metrics_svc.record(
            provider_id=provider_id,
            endpoint="/proxy/options",
            latency_ms=latency_ms,
            success=False,
            error_message=str(exc),
        )
        raise AppError(
            f"Upstream provider '{provider_id}' failed: {exc}",
            status_code=502,
        ) from exc


@router.get("/{provider_id}/proxy/quote")
def proxy_quote(
    provider_id: str,
    response: Response,
    symbol: str = Query(..., description="Ticker symbol"),
    svc: ProviderService = Depends(get_provider_service),
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict:
    """Fetch current quote through a specific provider."""
    registry = svc._registry
    entry = registry.get_entry(provider_id)
    if entry is None:
        raise NotFoundError("Provider", provider_id)

    if not entry.config.get("enabled", True):
        raise AppError(
            f"Provider '{provider_id}' is disabled", status_code=503
        )

    if not entry.circuit_breaker.allow_request():
        raise AppError(
            f"Provider '{provider_id}' is in circuit breaker cooldown",
            status_code=503,
        )

    if registry.is_rate_limited(provider_id):
        raise AppError(
            f"Rate limit exceeded for provider '{provider_id}'",
            status_code=429,
        )

    provider = entry.provider
    if provider is None:
        raise AppError(
            f"Provider '{provider_id}' type not supported for proxy calls",
            status_code=502,
        )

    start = time.monotonic()
    try:
        quote = provider.get_quote(symbol.upper())
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.record_success(provider_id)
        registry.record_call(provider_id)

        metrics_svc.record(
            provider_id=provider_id,
            endpoint="/proxy/quote",
            latency_ms=latency_ms,
            success=True,
        )

        _inject_provider_headers(response, registry, provider_id)

        return {
            "status": "ok",
            "symbol": symbol.upper(),
            "price": quote.price,
            "change": round(quote.price - quote.previous_close, 2),
            "changePercent": round(
                ((quote.price - quote.previous_close) / quote.previous_close * 100)
                if quote.previous_close
                else 0,
                2,
            ),
            "volume": quote.volume,
            "open": quote.day_low,  # approximation
            "high": quote.day_high,
            "low": quote.day_low,
            "previousClose": quote.previous_close,
            "provider": provider_id,
        }
    except AppError:
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.record_failure(provider_id)
        metrics_svc.record(
            provider_id=provider_id,
            endpoint="/proxy/quote",
            latency_ms=latency_ms,
            success=False,
            error_message=str(exc),
        )
        raise AppError(
            f"Upstream provider '{provider_id}' failed: {exc}",
            status_code=502,
        ) from exc


# ------------------------------------------------------------------
# Provider Metrics Endpoint (Issue #7)
# ------------------------------------------------------------------


@router.get("/{provider_id}/metrics")
def provider_metrics(
    provider_id: str,
    timeRange: str = Query(
        default="day", description="Time range: hour, day, week, month"
    ),
    svc: ProviderService = Depends(get_provider_service),
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict:
    """Return aggregated metrics for a specific provider."""
    # Validate provider exists
    svc.get_provider(provider_id)

    metrics = metrics_svc.get_metrics(provider_id, time_range=timeRange)
    top_errors = metrics_svc.get_top_errors(provider_id, limit=5)
    metrics["topErrors"] = top_errors
    return {"status": "ok", **metrics}


@router.get("/metrics/summary", tags=["Provider Metrics"])
def all_providers_metrics(
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict:
    """Return aggregated metrics summary for all providers."""
    return {
        "status": "ok",
        "providers": metrics_svc.get_all_providers_summary(),
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _inject_provider_headers(
    response: Response,
    registry,  # ProviderRegistry
    provider_id: str,
) -> None:
    """Set X-RateLimit-* and X-Provider-* response headers."""
    info = registry.get_rate_limit_info(provider_id)
    if info:
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
        response.headers["X-RateLimit-Window"] = info.get("window", "hour")

    response.headers["X-Provider-ID"] = provider_id

    # Determine provider status
    entry = registry.get_entry(provider_id)
    if entry:
        if not entry.circuit_breaker.allow_request():
            status = "degraded"
        elif registry.is_rate_limited(provider_id):
            status = "rate-limited"
        else:
            status = "connected"
    else:
        status = "unknown"
    response.headers["X-Provider-Status"] = status
