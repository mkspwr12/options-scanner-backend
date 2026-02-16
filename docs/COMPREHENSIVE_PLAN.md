# Comprehensive Implementation Plan

> **Generated**: 2026-02-15  
> **Baseline**: 327 tests passing, 85% coverage, v3.0.0  
> **Scope**: All 9 open GitHub issues — rearchitected into a coherent delivery plan

---

## 1. Current Architecture Assessment

### What Exists (v3.0.0)

```
app/
├── main.py                  # FastAPI entry, middleware, background scanner
├── config.py                # Settings from env vars (dataclass)
├── db.py                    # Azure SQL via pyodbc + Managed Identity
├── dependencies.py          # DI factory (singleton provider/circuit breaker)
├── exceptions.py            # AppError hierarchy + global handlers
├── models.py                # Pydantic domain models
├── schemas.py               # Request validation models
├── middleware/
│   ├── auth.py              # API key auth (X-API-Key header)
│   └── rate_limit.py        # In-memory sliding-window rate limiter
├── providers/
│   ├── base.py              # MarketDataProvider protocol
│   ├── yahoo_provider.py    # yfinance integration
│   ├── mock_provider.py     # Deterministic test data
│   ├── greeks.py            # Black-Scholes calculator
│   ├── scoring.py           # 5-factor composite scoring
│   └── circuit_breaker.py   # 3-state circuit breaker
├── repositories/
│   ├── trade_repository.py  # trades table CRUD
│   ├── scan_repository.py   # scan_results table read/write
│   └── watchlist_repository.py  # watchlist_items table CRUD
├── routers/
│   ├── health.py            # /healthz, /health, /api/diagnostics
│   ├── scan.py              # /api/scan, /api/scan/trigger, /api/multi-leg-opportunities
│   ├── trades.py            # /api/trades/track, /api/trades/close, /api/portfolio
│   ├── watchlist.py         # /api/watchlist, /api/watchlist/add, /api/watchlist/remove
│   └── logs.py              # /api/logs
└── services/
    ├── scan_service.py      # Scan orchestration + scoring pipeline
    ├── trade_service.py     # Trade tracking business logic
    ├── portfolio_service.py # Portfolio aggregation
    └── watchlist_service.py # Watchlist management
```

**Database** (Azure SQL Server, 3 tables):
- `trades` — single-leg trade positions
- `scan_results` — persisted scan opportunities
- `watchlist_items` — ticker symbols

**Provider Architecture**: Single hardcoded provider (Yahoo or Mock), selected by env var at startup. No multi-provider support, no runtime switching, no provider CRUD.

### Architecture Gaps Identified

| Gap | Impact | Issues Affected |
|-----|--------|----------------|
| **No provider registry** — single hardcoded provider | Cannot add/remove/switch providers at runtime | #2, #3, #4 |
| **No options-chain endpoint** — frontend gets 404 | Core feature broken for end users | #1 |
| **No multi-provider failover** — circuit breaker is per-provider only | Single point of failure for market data | #4 |
| **No advanced scan filters** — only basic symbol/type/confidence filters | Frontend filtering UI non-functional | #5 |
| **No multi-leg strategy persistence** — only sample data | Strategy builder can't save to DB | #6 |
| **No provider metrics tracking** — no call/latency/error recording | Can't monitor provider health historically | #7 |
| **No portfolio risk endpoint** — client-side Greek aggregation only | Performance bottleneck with 50+ positions | #8 |
| **No rate-limit response headers** — client can't see quota remaining | Client-side throttling blind | #9 |
| **Provider credentials not encrypted** — no key storage at all | Security gap for multi-provider | #2 |

### Rearchitecture Decision

**The 9 issues are NOT independent features**. They form a **Provider Platform** that must be designed as a cohesive system:

```
Issues #2 + #3 + #4 + #7 + #9 = Provider Management Platform
Issue #1 = Options Chain Endpoint (depends on provider platform)
Issue #5 = Scan Filter Enhancement (independent)
Issue #6 = Multi-Leg Strategy Persistence (independent)
Issue #8 = Portfolio Risk API (depends on #6 for multi-leg data)
```

---

## 2. Rearchitected Solution Design

### Target Architecture (v4.0.0)

```
app/
├── main.py                    # Entry point (unchanged structure)
├── config.py                  # + encryption key, provider defaults
├── db.py                      # Unchanged
├── dependencies.py            # + provider_service, options_chain_service DI
├── exceptions.py              # + ProviderError, RateLimitError
├── models.py                  # + Provider, Strategy, RiskAlert models
├── schemas.py                 # + ProviderRequest, StrategyRequest, ScanFilter schemas
│
├── middleware/
│   ├── auth.py                # Unchanged
│   └── rate_limit.py          # Unchanged (global rate limit stays)
│
├── providers/
│   ├── base.py                # + get_expiration_dates() method
│   ├── yahoo_provider.py      # + get_expiration_dates() impl
│   ├── mock_provider.py       # + get_expiration_dates() impl
│   ├── greeks.py              # Unchanged
│   ├── scoring.py             # Unchanged
│   ├── circuit_breaker.py     # Unchanged
│   ├── registry.py            # NEW: Runtime provider registry + failover
│   └── encryption.py          # NEW: Fernet-based API key encryption
│
├── repositories/
│   ├── trade_repository.py    # Unchanged
│   ├── scan_repository.py     # + advanced filter query support
│   ├── watchlist_repository.py # Unchanged
│   ├── provider_repository.py # NEW: providers table CRUD
│   ├── strategy_repository.py # NEW: strategies + strategy_legs tables
│   └── metrics_repository.py  # NEW: provider_metrics table
│
├── routers/
│   ├── health.py              # Unchanged
│   ├── scan.py                # + 13 filter query params (Issue #5)
│   ├── trades.py              # Unchanged
│   ├── watchlist.py           # Unchanged
│   ├── logs.py                # Unchanged
│   ├── providers.py           # NEW: CRUD + test + proxy + metrics (Issues #2,3,4,7)
│   ├── options_chain.py       # NEW: /api/options-chain/{ticker} (Issue #1)
│   ├── strategies.py          # NEW: /api/portfolio/strategies CRUD (Issue #6)
│   └── portfolio_risk.py      # NEW: /api/portfolio/risk (Issue #8)
│
└── services/
    ├── scan_service.py        # + advanced filtering logic
    ├── trade_service.py       # Unchanged
    ├── portfolio_service.py   # + risk aggregation methods
    ├── watchlist_service.py   # Unchanged
    ├── provider_service.py    # NEW: Provider mgmt + connection testing
    ├── options_chain_service.py # NEW: Options chain via provider registry
    ├── strategy_service.py    # NEW: Multi-leg strategy CRUD + validation
    └── metrics_service.py     # NEW: Provider metrics collection + aggregation

migrations/
├── 001_create_trades.sql          # Existing
├── 002_create_watchlist.sql       # Existing
├── 003_create_scan_results.sql    # Existing
├── 004_create_providers.sql       # NEW
├── 005_create_strategies.sql      # NEW
├── 006_create_provider_metrics.sql # NEW
├── 007_add_scan_filter_indexes.sql # NEW
```

### Key Design Decisions

1. **Provider Registry Pattern** — A `ProviderRegistry` class manages all configured providers at runtime. It holds per-provider `CircuitBreaker` instances and implements ordered failover based on priority. This replaces the singleton `_get_provider()` in `dependencies.py`.

2. **Encryption at Rest** — Provider API keys stored encrypted using `cryptography.fernet.Fernet` with key from `ENCRYPTION_KEY` env var. Masked in all GET responses (last 4 chars only).

3. **Provider Metrics as Middleware-like Decorator** — Every proxy call records latency, success/error, and endpoint to `provider_metrics` table. Aggregation queries use SQL window functions for percentiles.

4. **Scan Filters Applied In-Memory** — Scan results fetched from DB or live provider, then filtered in Python. This avoids complex dynamic SQL and enables caching. For DB-sourced results, filters pushed to SQL WHERE clause.

5. **Strategies as First-Class Entity** — New `strategies` + `strategy_legs` tables. Separate from `trades` table to maintain backward compatibility. Later, strategies can link to trades for P&L tracking.

6. **Rate-Limit Headers via Response Hook** — Injected at the router level (not middleware) because they're provider-specific. Each proxy endpoint adds `X-RateLimit-*` headers from the provider's counter.

---

## 3. Implementation Phases

### Phase 1: Provider Foundation (Issues #2, #3) — P0 Critical
**Estimated effort**: 3-4 sessions  
**Dependency**: None — this unblocks everything else

#### New Files
| File | Purpose |
|------|---------|
| `app/providers/encryption.py` | Fernet encrypt/decrypt for API keys |
| `app/providers/registry.py` | Runtime provider registry with per-provider circuit breakers |
| `app/repositories/provider_repository.py` | CRUD for `providers` table |
| `app/services/provider_service.py` | Provider management business logic |
| `app/routers/providers.py` | REST endpoints for provider CRUD + connection test |
| `app/schemas.py` (extend) | `CreateProviderRequest`, `UpdateProviderRequest`, `TestConnectionRequest` |
| `app/models.py` (extend) | `Provider`, `RateLimit`, `ConnectionTestResult` models |
| `migrations/004_create_providers.sql` | Provider table DDL |
| `tests/unit/test_encryption.py` | Encryption round-trip tests |
| `tests/unit/test_provider_registry.py` | Registry + failover tests |
| `tests/unit/test_provider_repository.py` | Provider CRUD data access tests |
| `tests/unit/test_provider_service.py` | Provider service business logic tests |
| `tests/integration/test_providers_api.py` | Provider API integration tests |

#### Database Schema
```sql
CREATE TABLE providers (
    id                      VARCHAR(50)    PRIMARY KEY,
    name                    VARCHAR(100)   NOT NULL UNIQUE,
    type                    VARCHAR(20)    NOT NULL,  -- YAHOO_FINANCE, ALPACA, TRADIER, CUSTOM
    api_key_encrypted       VARBINARY(MAX) NULL,
    api_secret_encrypted    VARBINARY(MAX) NULL,
    base_url                VARCHAR(255)   NOT NULL,
    enabled                 BIT            NOT NULL DEFAULT 1,
    priority                INT            NOT NULL,
    rate_limit_max_per_hour INT            DEFAULT 2000,
    rate_limit_max_per_day  INT            DEFAULT 20000,
    rate_limit_cost_per_call DECIMAL(10,4) DEFAULT 0,
    created_at              DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
    updated_at              DATETIME2      NOT NULL DEFAULT GETUTCDATE()
);
CREATE INDEX ix_providers_priority ON providers(priority);
```

#### API Endpoints
| Method | Path | Status Code | Description |
|--------|------|-------------|-------------|
| GET | `/api/providers` | 200 | List all providers (masked keys) |
| POST | `/api/providers` | 201 | Create new provider |
| PUT | `/api/providers/{id}` | 200 | Update provider config |
| DELETE | `/api/providers/{id}` | 204 | Delete provider (not last one) |
| POST | `/api/providers/{id}/test` | 200 | Test provider connection |

#### Acceptance Criteria
- [ ] Full CRUD for providers with encrypted API key storage
- [ ] API keys masked in responses (show only last 4 chars)
- [ ] Input validation: type enum, URL format, rate limit bounds
- [ ] Cannot delete the last remaining provider (409 Conflict)
- [ ] Connection test with 10s timeout, descriptive error messages
- [ ] Provider-specific test endpoints (Yahoo → /chart, Alpaca → /account)
- [ ] Test connection supports both saved and unsaved credentials
- [ ] 40+ new tests, maintains ≥85% coverage

#### Modified Files
- `app/dependencies.py` — Add `get_provider_service()` factory
- `app/main.py` — Register `providers.router`
- `app/config.py` — Add `encryption_key` setting
- `app/exceptions.py` — Add `ProviderError` exception
- `requirements.txt` — Add `cryptography`

---

### Phase 2: Provider Proxy + Options Chain (Issues #4, #1) — P0/P1
**Estimated effort**: 2-3 sessions  
**Dependency**: Phase 1 (provider registry must exist)

#### New Files
| File | Purpose |
|------|---------|
| `app/services/options_chain_service.py` | Options chain retrieval via registry |
| `app/routers/options_chain.py` | `GET /api/options-chain/{ticker}` |
| `app/routers/providers.py` (extend) | Proxy endpoints added to existing router |
| `app/providers/base.py` (extend) | Add `get_expiration_dates()` to protocol |
| `tests/unit/test_options_chain_service.py` | Options chain service tests |
| `tests/integration/test_options_chain_api.py` | Options chain API tests |
| `tests/integration/test_provider_proxy_api.py` | Proxy endpoint tests |

#### API Endpoints
| Method | Path | Status Code | Description |
|--------|------|-------------|-------------|
| GET | `/api/options-chain/{ticker}` | 200 | Fetch options chain (auto-selects best provider) |
| GET | `/api/providers/{id}/proxy/options` | 200 | Proxy options chain via specific provider |
| GET | `/api/providers/{id}/proxy/quote` | 200 | Proxy quote via specific provider |

#### Response Schema (Options Chain)
```json
{
  "ticker": "MSFT",
  "underlyingPrice": 415.30,
  "expirationDates": ["2026-02-20", "2026-02-27"],
  "contracts": [{
    "contractSymbol": "MSFT260220C00400000",
    "strike": 400.0,
    "expiration": "2026-02-20",
    "optionType": "call",
    "bid": 16.10, "ask": 16.50, "last": 16.30,
    "volume": 1234, "openInterest": 5678,
    "impliedVolatility": 0.28,
    "delta": 0.72, "gamma": 0.015, "theta": -0.45, "vega": 0.32,
    "inTheMoney": true
  }],
  "lastUpdated": "2026-02-15T12:00:00Z",
  "dataDelayMinutes": 15
}
```

#### Key Logic
- Options chain endpoint uses `ProviderRegistry.get_best_provider()` for auto-failover
- Proxy endpoints lookup provider by ID, verify enabled + not in circuit breaker cooldown
- Provider credentials injected server-side (never exposed to client)
- Error mapping: 400 (bad ticker), 404 (no provider), 429 (rate limited), 502 (upstream fail), 503 (provider disabled)
- Greeks calculated via existing `calculate_greeks()` and attached to each contract

#### Acceptance Criteria
- [ ] `GET /api/options-chain/{ticker}` returns full options chain with Greeks
- [ ] Response matches frontend `OptionsChain` TypeScript interface
- [ ] Provider proxy endpoints route through specific providers with credential injection
- [ ] Error responses use proper HTTP status codes (400, 404, 429, 502, 503)
- [ ] Failover: if primary provider fails, auto-tries next by priority
- [ ] 30+ new tests

#### Modified Files
- `app/providers/base.py` — Add `get_expiration_dates()` method
- `app/providers/yahoo_provider.py` — Implement `get_expiration_dates()`
- `app/providers/mock_provider.py` — Implement `get_expiration_dates()`
- `app/main.py` — Register `options_chain.router`
- `app/dependencies.py` — Add `get_options_chain_service()` factory

---

### Phase 3: Advanced Scan Filters (Issue #5) — P1
**Estimated effort**: 1-2 sessions  
**Dependency**: None (independent)

#### Modified Files
| File | Change |
|------|--------|
| `app/routers/scan.py` | Add 13 filter query params with FastAPI `Query()` validation |
| `app/services/scan_service.py` | Add `_apply_filters()` method for in-memory filtering |
| `app/repositories/scan_repository.py` | Extend SQL WHERE clause for Greek/DTE/volume filters |
| `app/schemas.py` | Add `ScanFilterParams` model |
| `migrations/007_add_scan_filter_indexes.sql` | Add indexes on delta, theta, vega, implied_volatility |
| `tests/unit/test_scan_service.py` | Add filter combination tests |
| `tests/integration/test_scan_api.py` | Add filter query param tests |

#### Filter Parameters
| Parameter | Type | Range | Default |
|-----------|------|-------|---------|
| `iv_min` / `iv_max` | float | 0-100 | None |
| `dte_min` / `dte_max` | int | 0-365 | None |
| `vol_oi_min` / `vol_oi_max` | float | 0-10 | None |
| `delta_min` / `delta_max` | float | -1.0 to 1.0 | None |
| `theta_min` / `theta_max` | float | -5.0 to 0.0 | None |
| `vega_min` / `vega_max` | float | 0-2.0 | None |
| `option_type` | enum | call/put/all | all |
| `moneyness` | enum | itm/otm/atm/all | all |
| `min_volume` | int | ≥0 | None |

#### Key Logic
- No params → return all (backward compatible)
- Invalid values → 422 via FastAPI validation
- Filters applied both in SQL (when reading from DB) and in-memory (when from live scan)
- Response format unchanged: `{"opportunities": [...]}`

#### Acceptance Criteria
- [ ] All 13 query parameters accepted and validated
- [ ] Filters compose with AND logic (all must match)
- [ ] Empty result set returns `{"opportunities": []}`
- [ ] No params → all results (backward compatible)
- [ ] Performance: <2s for 500+ results
- [ ] 20+ new tests

---

### Phase 4: Multi-Leg Strategy Tracking (Issue #6) — P2
**Estimated effort**: 2-3 sessions  
**Dependency**: None (independent, but enables Phase 5)

#### New Files
| File | Purpose |
|------|---------|
| `app/repositories/strategy_repository.py` | CRUD for strategies + strategy_legs tables |
| `app/services/strategy_service.py` | Strategy validation, P&L calc, CRUD |
| `app/routers/strategies.py` | Strategy REST endpoints |
| `app/models.py` (extend) | `Strategy`, `StrategyLeg`, `StrategyMetrics` models |
| `app/schemas.py` (extend) | `CreateStrategyRequest`, `UpdateStrategyRequest` |
| `migrations/005_create_strategies.sql` | strategies + strategy_legs DDL |
| `tests/unit/test_strategy_repository.py` | Repository tests |
| `tests/unit/test_strategy_service.py` | Service tests (validation, P&L, Greek agg) |
| `tests/integration/test_strategies_api.py` | API integration tests |

#### Database Schema
```sql
CREATE TABLE strategies (
    id                  VARCHAR(50)    PRIMARY KEY,
    strategy_type       VARCHAR(50)    NOT NULL,
    name                VARCHAR(200)   NULL,
    ticker              VARCHAR(10)    NOT NULL,
    underlying_price    DECIMAL(10,2)  NULL,
    max_profit          DECIMAL(12,2)  NULL,
    max_loss            DECIMAL(12,2)  NULL,
    breakevens          NVARCHAR(MAX)  NULL,  -- JSON array
    risk_reward         DECIMAL(6,2)   NULL,
    net_debit           DECIMAL(12,2)  NULL,
    net_credit          DECIMAL(12,2)  NULL,
    unrealized_pl       DECIMAL(12,2)  NULL,
    unrealized_pl_pct   DECIMAL(6,2)   NULL,
    status              VARCHAR(20)    DEFAULT 'active',
    entry_date          DATETIME2      DEFAULT GETUTCDATE(),
    exit_date           DATETIME2      NULL,
    last_updated        DATETIME2      DEFAULT GETUTCDATE(),
    tags                NVARCHAR(MAX)  NULL,  -- JSON array
    notes               NVARCHAR(MAX)  NULL
);

CREATE TABLE strategy_legs (
    id              INT             IDENTITY(1,1) PRIMARY KEY,
    strategy_id     VARCHAR(50)     NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    leg_order       INT             NOT NULL,
    option_type     VARCHAR(10)     NOT NULL,
    strike          DECIMAL(10,2)   NOT NULL,
    expiration      DATE            NOT NULL,
    action          VARCHAR(10)     NOT NULL,  -- buy or sell
    quantity        INT             NOT NULL,
    entry_price     DECIMAL(10,4)   NULL,
    current_price   DECIMAL(10,4)   NULL,
    delta           DECIMAL(6,4)    NULL,
    gamma           DECIMAL(6,4)    NULL,
    theta           DECIMAL(6,4)    NULL,
    vega            DECIMAL(6,4)    NULL,
    implied_vol     DECIMAL(6,4)    NULL
);

CREATE INDEX ix_strategies_ticker ON strategies(ticker);
CREATE INDEX ix_strategies_status ON strategies(status);
CREATE INDEX ix_strategy_legs_sid ON strategy_legs(strategy_id);
```

#### API Endpoints
| Method | Path | Status Code | Description |
|--------|------|-------------|-------------|
| POST | `/api/portfolio/strategies` | 201 | Create multi-leg strategy |
| GET | `/api/portfolio/strategies` | 200 | List strategies (with filters) |
| GET | `/api/portfolio/strategies/{id}` | 200 | Get strategy detail |
| PUT | `/api/portfolio/strategies/{id}` | 200 | Update strategy |
| DELETE | `/api/portfolio/strategies/{id}` | 204 | Close/remove strategy |

#### Strategy Types Supported
`vertical-spread`, `iron-condor`, `straddle`, `strangle`, `butterfly`, `calendar`, `diagonal`, `custom`

#### Validation Rules
- 2-4 legs required
- All legs same ticker
- Buy/sell quantities must form valid position
- Expiration consistency (calendar spreads allow different expirations)

#### Acceptance Criteria
- [ ] Full CRUD for multi-leg strategies
- [ ] 8 strategy types supported
- [ ] Validates leg count, ticker consistency, expiration logic
- [ ] Calculates unrealized P&L by summing leg P&Ls
- [ ] Aggregates Greeks across legs (weighted by quantity and action)
- [ ] 35+ new tests

---

### Phase 5: Portfolio Risk & Provider Metrics (Issues #8, #7) — P2/P3
**Estimated effort**: 2-3 sessions  
**Dependency**: Phase 4 (strategy data for risk aggregation)

#### New Files
| File | Purpose |
|------|---------|
| `app/routers/portfolio_risk.py` | `GET /api/portfolio/risk` |
| `app/repositories/metrics_repository.py` | provider_metrics table CRUD |
| `app/services/metrics_service.py` | Metrics collection + aggregation |
| `migrations/006_create_provider_metrics.sql` | provider_metrics DDL |
| `tests/unit/test_metrics_service.py` | Metrics aggregation tests |
| `tests/unit/test_portfolio_risk.py` | Risk calculation tests |
| `tests/integration/test_portfolio_risk_api.py` | Risk API tests |
| `tests/integration/test_provider_metrics_api.py` | Metrics API tests |

#### Provider Metrics Schema
```sql
CREATE TABLE provider_metrics (
    id              INT             IDENTITY(1,1) PRIMARY KEY,
    provider_id     VARCHAR(50)     NOT NULL,
    timestamp       DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    latency_ms      INT             NOT NULL,
    success         BIT             NOT NULL,
    error           NVARCHAR(500)   NULL,
    endpoint        VARCHAR(100)    NULL
);
CREATE INDEX ix_pm_provider_time ON provider_metrics(provider_id, timestamp DESC);
```

#### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/risk` | Aggregated portfolio Greeks + risk alerts |
| GET | `/api/providers/{id}/metrics` | Provider metrics (latency, errors, counts) |
| GET | `/api/providers/metrics/summary` | All providers metrics summary |

#### Portfolio Risk Response
- `summary` — Total delta/gamma/theta/vega, portfolio value, P&L
- `positions` — Per-position details with leg breakdown
- `riskAlerts` — Threshold violations (info/warning/critical)
- `byStrategy` / `byTicker` — Grouping options

#### Acceptance Criteria
- [ ] Portfolio risk endpoint aggregates Greeks across all active positions + strategies
- [ ] Supports `groupBy` parameter (none, strategy, ticker)
- [ ] Risk alerts evaluate configurable thresholds
- [ ] Provider metrics track latency, success/error counts, top errors
- [ ] Metrics support time ranges (hour, day, week, month)
- [ ] Cached with 30s TTL (risk) / 60s TTL (metrics)
- [ ] 30+ new tests

---

### Phase 6: Rate-Limit Response Headers (Issue #9) — P3
**Estimated effort**: 1 session  
**Dependency**: Phase 1 (provider rate limit config), Phase 2 (proxy endpoints)

#### Modified Files
| File | Change |
|------|--------|
| `app/providers/registry.py` | Add per-provider call counter with hourly window |
| `app/routers/providers.py` | Inject `X-RateLimit-*` headers on proxy responses |
| `app/routers/options_chain.py` | Inject `X-RateLimit-*` headers |
| `app/exceptions.py` | Add `RateLimitError` with `Retry-After` |
| `tests/unit/test_rate_limit_headers.py` | Header injection tests |
| `tests/integration/test_rate_limit_headers_api.py` | API header tests |

#### Headers Added
```
X-RateLimit-Limit: 2000
X-RateLimit-Remaining: 1750
X-RateLimit-Reset: 3600
X-RateLimit-Window: hour
X-Provider-ID: yahoo-default
X-Provider-Status: connected
```

#### Key Logic
- In-memory sliding-window counter per provider ID
- Counter keyed by `provider_id:hour_bucket`  
- When `remaining == 0`, return 429 with `Retry-After`
- On failover, headers reflect the active (fallback) provider

#### Acceptance Criteria
- [ ] All proxy + options-chain endpoints include rate-limit headers
- [ ] `X-RateLimit-Remaining` decreases on each call
- [ ] 429 response includes `Retry-After`
- [ ] Failover scenario shows `X-Provider-Failover: true`
- [ ] 15+ new tests

---

## 4. Dependency Graph

```
Phase 1 (Provider CRUD + Test)    Phase 3 (Scan Filters)    Phase 4 (Strategies)
    │                                  │ (independent)           │
    ▼                                  │                         │
Phase 2 (Proxy + Options Chain)        │                         ▼
    │                                  │                   Phase 5 (Risk + Metrics)
    ▼                                  │                         │
Phase 6 (Rate-Limit Headers) ◄────────┘                         │
    │                                                            │
    └────────────────────────┬───────────────────────────────────┘
                             ▼
                      v4.0.0 Release
```

**Parallel Tracks**:
- Track A: Phase 1 → Phase 2 → Phase 6 (Provider Platform)
- Track B: Phase 3 (Scan Filters — anytime)
- Track C: Phase 4 → Phase 5 (Strategy + Risk — anytime)

---

## 5. File Impact Summary

### New Files (22)
| Category | Files |
|----------|-------|
| **Source** | `providers/encryption.py`, `providers/registry.py`, `repositories/provider_repository.py`, `repositories/strategy_repository.py`, `repositories/metrics_repository.py`, `services/provider_service.py`, `services/options_chain_service.py`, `services/strategy_service.py`, `services/metrics_service.py`, `routers/providers.py`, `routers/options_chain.py`, `routers/strategies.py`, `routers/portfolio_risk.py` |
| **Migrations** | `004_create_providers.sql`, `005_create_strategies.sql`, `006_create_provider_metrics.sql`, `007_add_scan_filter_indexes.sql` |
| **Tests** | `test_encryption.py`, `test_provider_registry.py`, `test_provider_repository.py`, `test_provider_service.py`, `test_options_chain_service.py`, `test_strategy_repository.py`, `test_strategy_service.py`, `test_metrics_service.py`, `test_portfolio_risk.py`, `test_providers_api.py`, `test_options_chain_api.py`, `test_provider_proxy_api.py`, `test_strategies_api.py`, `test_portfolio_risk_api.py`, `test_provider_metrics_api.py`, `test_rate_limit_headers.py`, `test_rate_limit_headers_api.py` |

### Modified Files (12)
| File | Phases |
|------|--------|
| `app/main.py` | 1, 2, 4, 5 (register new routers) |
| `app/config.py` | 1 (add encryption_key) |
| `app/dependencies.py` | 1, 2, 4, 5 (new DI factories) |
| `app/exceptions.py` | 1, 6 (new exception types) |
| `app/models.py` | 1, 4, 5 (new domain models) |
| `app/schemas.py` | 1, 3, 4 (new request schemas) |
| `app/providers/base.py` | 2 (add get_expiration_dates) |
| `app/providers/yahoo_provider.py` | 2 (implement new method) |
| `app/providers/mock_provider.py` | 2 (implement new method) |
| `app/routers/scan.py` | 3 (add filter params) |
| `app/services/scan_service.py` | 3 (add filter logic) |
| `app/repositories/scan_repository.py` | 3 (extend SQL where) |
| `requirements.txt` | 1 (add cryptography) |

---

## 6. Testing Strategy

### Test Targets
| Phase | New Tests | Cumulative Total | Coverage Target |
|-------|-----------|------------------|-----------------|
| Current | — | 327 | 85% |
| Phase 1 | ~45 | ~372 | ≥85% |
| Phase 2 | ~35 | ~407 | ≥85% |
| Phase 3 | ~25 | ~432 | ≥86% |
| Phase 4 | ~40 | ~472 | ≥86% |
| Phase 5 | ~35 | ~507 | ≥87% |
| Phase 6 | ~18 | ~525 | ≥87% |

### Testing Patterns (Consistent with Existing)
- **Unit tests**: Mock `pyodbc.connect` via `unittest.mock.patch`
- **Integration tests**: TestClient with stubbed repositories (same as `conftest.py`)
- **Provider tests**: MockProvider for deterministic assertions
- **No external calls**: All tests run offline, all DB calls mocked

---

## 7. Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Encryption key rotation breaks existing data | Low | High | Use key versioning — store key ID alongside ciphertext |
| Provider failover cascading failures | Medium | Medium | Per-provider circuit breakers with separate timeouts |
| SQL Server JSON support limitations | Low | Medium | Use NVARCHAR(MAX) for JSON fields, parse in Python |
| Rate-limit counters lost on restart | Medium | Low | Acceptable for MVP — counters reset on deploy |
| Strategy validation false negatives | Medium | Low | Conservative: reject malformed, allow `custom` type escape hatch |

---

## 8. Priority Execution Order

| Order | Phase | Issues | Priority | Blocks |
|-------|-------|--------|----------|--------|
| 1st | Phase 1 | #2, #3 | P0 | Phase 2, Phase 6 |
| 2nd | Phase 2 | #4, #1 | P0/P1 | Phase 6 |
| 3rd | Phase 3 | #5 | P1 | Nothing |
| 4th | Phase 4 | #6 | P2 | Phase 5 |
| 5th | Phase 5 | #7, #8 | P2/P3 | Nothing |
| 6th | Phase 6 | #9 | P3 | Nothing |

**Total estimated new tests**: ~198  
**Total estimated new source files**: 13  
**Total estimated new migration files**: 4  
**New dependency**: `cryptography` (for Fernet encryption)

---

## 9. Issue-to-Phase Mapping

| Issue | Title | Priority | Phase | Status |
|-------|-------|----------|-------|--------|
| #1 | Missing `/api/options-chain/{ticker}` endpoint | — | Phase 2 | Not Started |
| #2 | Provider CRUD API | P0 | Phase 1 | Not Started |
| #3 | Provider Connection Testing | P0 | Phase 1 | Not Started |
| #4 | Provider Proxy Endpoints | P1 | Phase 2 | Not Started |
| #5 | Advanced Scan Filters | P1 | Phase 3 | Not Started |
| #6 | Multi-Leg Strategy Tracking | P2 | Phase 4 | Not Started |
| #7 | Server-Side Provider Metrics | P2 | Phase 5 | Not Started |
| #8 | Portfolio Greek Aggregation | P3 | Phase 5 | Not Started |
| #9 | Rate Limit Response Headers | P3 | Phase 6 | Not Started |
