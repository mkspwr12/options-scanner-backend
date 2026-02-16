# Comprehensive Implementation Plan — Backend Issues #1-#5

**Document Version**: 1.0  
**Date**: February 15, 2026  
**Issues Covered**: #1 (Options Chain), #2 (Provider CRUD), #3 (Connection Testing), #4 (Provider Proxy), #5 (Advanced Filters)

---

## Executive Summary

**Total Issues**: 5 (1 bug, 4 features)  
**Priority Breakdown**: 2 P0 (critical), 2 P1 (high), 1 enhancement  
**Estimated Effort**: 18-24 development days  
**Risk Level**: Medium (requires database schema changes + new architecture layer)

### Critical Dependencies
1. **Issue #2 (Provider CRUD)** blocks #3 and #4 — must implement first
2. **Issue #3 (Connection Testing)** depends on #2's provider storage
3. **Issue #4 (Provider Proxy)** depends on #2's provider storage
4. **Issue #1 and #5** are independent, can be done in parallel

---

## Phase 1: Architecture Analysis & Planning (2-3 days)

### 1.1 New Architecture Components Needed

#### Database Layer
- **New Table**: `providers`
  - Columns: `id`, `name`, `type`, `api_key_encrypted`, `api_secret_encrypted`, `base_url`, `enabled`, `priority`, `rate_limit_max_per_hour`, `rate_limit_max_per_day`, `rate_limit_cost_per_call`, `created_at`, `updated_at`
  - Indexes: `idx_providers_priority`, `idx_providers_enabled`
  - Migration: `004_create_providers.sql`
  
- **New Table**: `provider_call_history` (for rate limiting tracking)
  - Columns: `id`, `provider_id`, `endpoint`, `timestamp`, `latency_ms`, `status_code`, `error_message`
  - Indexes: `idx_call_history_provider_timestamp`
  - Migration: `005_create_provider_call_history.sql`

#### Repository Layer (New)
- `app/repositories/provider_repository.py`
  - Methods: `get_all()`, `get_by_id()`, `create()`, `update()`, `delete()`, `increment_call_count()`, `get_call_count()`
  - Encryption helpers: `encrypt_api_key()`, `decrypt_api_key()`, `mask_api_key()`

#### Service Layer (New)
- `app/services/provider_service.py` — Manages provider CRUD + connection testing
- `app/services/provider_proxy_service.py` — Handles proxy requests to external APIs
- `app/services/options_chain_service.py` — Fetches options chain with Greeks computation (Issue #1)

#### Router Layer (New)
- `app/routers/providers.py` — CRUD endpoints (#2)
- `app/routers/provider_proxy.py` — Proxy endpoints (#4)
- `app/routers/options_chain.py` — Options chain endpoint (#1)

#### Model Layer (Extend Existing)
- `app/models.py`:
  - Add: `Provider`, `ProviderRateLimit`, `ProviderType` (enum), `ConnectionTestResult`
  - Add: `OptionsChainContract`, `OptionsChainResponse` (Issue #1)
  - Add: `ScanFilters` (Issue #5)

#### Provider Layer (Enhance Existing)
- `app/providers/base.py`:
  - Add method: `get_expiration_dates(symbol: str) -> list[str]`
  - Add adapter protocol for external APIs (Alpaca, Tradier, Custom)
  
- New files:
  - `app/providers/alpaca_provider.py`
  - `app/providers/tradier_provider.py`
  - `app/providers/provider_factory.py` — Dynamically instantiate providers from DB config

#### Middleware/Utilities (New)
- `app/utils/encryption.py` — API key encryption/decryption (Fernet or AES-256)
- `app/utils/rate_limiter.py` — Provider-specific rate limit enforcement
- `app/utils/contract_symbol_generator.py` — Generate OCC symbols (e.g., `MSFT260220C00400000`)

---

### 1.2 Quality Assurance Strategy

#### Code Quality Checks
1. **Type Hints**: 100% coverage for new code (use `mypy --strict`)
2. **Docstrings**: All public methods have Google-style docstrings
3. **Linting**: Pass `ruff check app/` with 0 errors
4. **Formatting**: `black app/` + `isort app/`

#### Test Coverage Targets
| Component | Unit Tests | Integration Tests | Min Coverage |
|-----------|------------|-------------------|--------------|
| Provider Repository | 15 tests | 5 tests (DB mocks) | 90% |
| Provider Service | 20 tests | 8 tests | 85% |
| Proxy Service | 18 tests | 10 tests (HTTP mocks) | 85% |
| Options Chain Service | 12 tests | 5 tests | 90% |
| Scan Filters | 25 tests | 8 tests | 95% |
| Encryption Utils | 10 tests | 0 (unit only) | 100% |
| **Overall Target** | **100 tests** | **36 tests** | **85%** |

#### Security Audit
- [ ] No hardcoded API keys in code
- [ ] Encryption keys stored in Azure Key Vault (not env vars)
- [ ] SQL injection prevention (parameterized queries)
- [ ] Input validation for all external-facing endpoints
- [ ] Rate limiting on all provider proxy endpoints

---

### 1.3 Error Handling Matrix

| Error Type | HTTP Status | Log Level | Response Format | Retry Strategy |
|------------|-------------|-----------|-----------------|----------------|
| Invalid ticker | 400 | WARNING | `{"status":"error","detail":"...","code":400}` | No retry |
| Provider not found | 404 | WARNING | `{"status":"error","detail":"...","code":404}` | No retry |
| Duplicate provider | 409 | WARNING | `{"status":"error","detail":"...","code":409}` | No retry |
| Rate limit exceeded | 429 | INFO | `{"status":"error","detail":"...","code":429,"retryAfter":3600}` | Exponential backoff |
| Upstream API failure | 502 | ERROR | `{"status":"error","detail":"...","code":502}` | Circuit breaker + failover |
| Database connection | 503 | CRITICAL | `{"status":"error","detail":"...","code":503}` | Retry 3x with backoff |
| Encryption failure | 500 | CRITICAL | `{"status":"error","detail":"Internal error","code":500}` | Alert + no retry |
| Timeout | 504 | WARNING | `{"status":"error","detail":"...","code":504}` | Retry once |

---

### 1.4 Logging Strategy

#### Structured Logging Format
```python
logger.info(
    "event",
    extra={
        "event_type": "provider_proxy_request",
        "provider_id": "yahoo-default",
        "symbol": "MSFT",
        "latency_ms": 245,
        "status_code": 200,
        "cache_hit": False
    }
)
```

#### Log Levels by Operation
| Operation | Success | Failure | Performance Issue |
|-----------|---------|---------|-------------------|
| Provider CRUD | INFO | WARNING | — |
| Connection Test | INFO | WARNING | — |
| Proxy Request | DEBUG | ERROR | WARNING (>5s latency) |
| Rate Limit Check | DEBUG | INFO (when blocked) | — |
| Encryption | DEBUG | CRITICAL | — |
| Database Query | DEBUG | ERROR | WARNING (>500ms) |

#### Retention & Monitoring
- **Application Insights**: All logs auto-sent (already configured)
- **In-Memory Store**: Last 1000 entries (already exists in `main.py`)
- **Alerts**: Set up Azure Monitor alerts for:
  - Encryption failures (CRITICAL logs)
  - Provider proxy 502 rate >10% (ERROR logs)
  - Database connection failures (CRITICAL logs)

---

## Phase 2: Foundation Work (5-6 days)

### Task 2.1: Database Schema & Migrations (1 day)

**Files to Create**:
- `migrations/004_create_providers.sql`
- `migrations/005_create_provider_call_history.sql`

**SQL Schema**:
```sql
-- 004_create_providers.sql
CREATE TABLE providers (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('YAHOO_FINANCE', 'ALPACA', 'TRADIER', 'CUSTOM')),
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    base_url VARCHAR(255) NOT NULL,
    enabled BIT DEFAULT 1,
    priority INT NOT NULL,
    rate_limit_max_per_hour INT DEFAULT 2000,
    rate_limit_max_per_day INT DEFAULT 20000,
    rate_limit_cost_per_call DECIMAL(10,4) DEFAULT 0,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);

CREATE INDEX idx_providers_priority ON providers(priority);
CREATE INDEX idx_providers_enabled ON providers(enabled);

-- Seed default Yahoo Finance provider
INSERT INTO providers (id, name, type, base_url, enabled, priority, rate_limit_max_per_hour, rate_limit_max_per_day)
VALUES ('yahoo-default', 'Yahoo Finance', 'YAHOO_FINANCE', 'https://query1.finance.yahoo.com', 1, 1, 2000, 20000);

-- 005_create_provider_call_history.sql
CREATE TABLE provider_call_history (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    provider_id VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    timestamp DATETIME2 DEFAULT GETUTCDATE(),
    latency_ms INT,
    status_code INT,
    error_message TEXT,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

CREATE INDEX idx_call_history_provider_timestamp ON provider_call_history(provider_id, timestamp);
```

**Validation**:
- Run migrations against dev Azure SQL database
- Verify seed data exists (`SELECT * FROM providers`)
- Test cascade delete with dummy provider

**Tests**: None (manual verification)

---

### Task 2.2: Encryption Utility (1 day)

**File**: `app/utils/encryption.py`

**Implementation**:
```python
from cryptography.fernet import Fernet
import os
import base64

class ProviderKeyEncryption:
    """Encrypt/decrypt provider API keys using Fernet symmetric encryption."""
    
    def __init__(self):
        # In production, load from Azure Key Vault
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        self._fernet = Fernet(key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt API key. Returns base64-encoded ciphertext."""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt API key. Returns plaintext."""
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    def mask(self, plaintext: str) -> str:
        """Mask API key (show only last 4 chars)."""
        if len(plaintext) <= 4:
            return "****"
        return "****" + plaintext[-4:]
```

**Tests** (`tests/unit/test_encryption.py`):
- Round-trip encryption/decryption
- Masking behavior (last 4 chars)
- Error when `ENCRYPTION_KEY` missing
- Error when decrypting invalid ciphertext
- Edge cases: empty string, unicode characters

**Coverage Target**: 100%

---

### Task 2.3: Provider Repository (1.5 days)

**File**: `app/repositories/provider_repository.py`

**Class**: `ProviderRepository`

**Methods**:
- `get_all(enabled_only: bool = False) -> list[Provider]`
- `get_by_id(provider_id: str) -> Provider` (raises `NotFoundError`)
- `get_by_priority() -> list[Provider]` (sorted by priority ascending)
- `create(data: dict) -> Provider` (encrypts keys, raises `ConflictError` if name exists)
- `update(provider_id: str, data: dict) -> Provider` (partial update)
- `delete(provider_id: str) -> None` (raises `ConflictError` if last enabled provider)
- `record_call(provider_id: str, endpoint: str, latency_ms: int, status_code: int, error: str = None) -> None`
- `get_hourly_call_count(provider_id: str) -> int`
- `get_daily_call_count(provider_id: str) -> int`

**Error Handling**:
- Database errors → raise `DatabaseError`
- Not found → raise `NotFoundError`
- Duplicate name → raise `ConflictError`
- Last provider deletion → raise `ConflictError("Cannot delete last enabled provider")`

**Tests** (`tests/unit/test_provider_repository.py`):
- CRUD operations with mocked `pyodbc`
- Encryption integration (verify encrypted values in DB)
- Priority sorting
- Conflict detection (duplicate name, last provider deletion)
- Rate limit call tracking

**Coverage Target**: 90%

---

### Task 2.4: Provider Service (1.5 days)

**File**: `app/services/provider_service.py`

**Class**: `ProviderService`

**Methods**:
- `list_providers(enabled_only: bool = False) -> list[dict]` (masks API keys)
- `get_provider(provider_id: str) -> dict` (masks API keys)
- `create_provider(data: dict) -> dict` (validates + encrypts + creates)
- `update_provider(provider_id: str, data: dict) -> dict` (validates + updates)
- `delete_provider(provider_id: str) -> None`
- `test_connection(provider_id: str, test_credentials: dict = None) -> ConnectionTestResult`

**Validation Logic** (in `create_provider`):
- `type` must be in `ProviderType` enum
- `base_url` must be valid HTTP/HTTPS URL
- `priority` must be positive integer
- `rate_limit_max_per_hour` ≥ 0
- `api_key` required for non-Yahoo providers

**Connection Test Logic** (`test_connection`):
```python
def test_connection(self, provider_id: str, test_credentials: dict = None) -> dict:
    """
    Test provider connectivity.
    
    Args:
        provider_id: Provider to test
        test_credentials: Optional credentials for unsaved providers
    
    Returns:
        {
            "success": bool,
            "latencyMs": int,
            "message": str or None,
            "error": str or None,
            "details": {...}
        }
    """
    start = time.monotonic()
    try:
        # 1. Get provider config (from DB or test_credentials)
        # 2. Build test endpoint based on provider type
        # 3. Make HTTP request (10s timeout)
        # 4. Validate response format
        # 5. Return success result
    except HTTPError as e:
        return {"success": False, "error": f"{e.status_code} {e.reason}", ...}
    except Timeout:
        return {"success": False, "error": "Connection timeout after 10 seconds", ...}
    except Exception as e:
        return {"success": False, "error": str(e), ...}
```

**Test Endpoints by Provider Type**:
| Type | Endpoint | Expected Response |
|------|----------|-------------------|
| `YAHOO_FINANCE` | `GET {baseUrl}/v8/finance/chart/AAPL` | 200 with valid JSON |
| `ALPACA` | `GET {baseUrl}/v2/account` (with auth headers) | 200 with account data |
| `TRADIER` | `GET {baseUrl}/v1/user/profile` (with Bearer token) | 200 with profile |
| `CUSTOM` | `GET {baseUrl}/healthz` | 200 |

**Tests** (`tests/unit/test_provider_service.py`):
- List/create/update/delete with mocked repository
- API key masking in responses
- Validation errors (invalid type, URL, etc.)
- Connection test success/failure scenarios (401, timeout, DNS error)
- HTTP mocking with `responses` library

**Coverage Target**: 85%

---

### Task 2.5: Models & Schemas (1 day)

**File**: `app/models.py` (extend)

**New Models**:
```python
from enum import Enum
from pydantic import BaseModel, Field

class ProviderType(str, Enum):
    YAHOO_FINANCE = "YAHOO_FINANCE"
    ALPACA = "ALPACA"
    TRADIER = "TRADIER"
    CUSTOM = "CUSTOM"

class ProviderRateLimit(BaseModel):
    maxPerHour: int = Field(ge=0)
    maxPerDay: int = Field(ge=0)
    costPerCall: float = Field(ge=0.0)

class Provider(BaseModel):
    id: str
    name: str
    type: ProviderType
    apiKeyMasked: str
    baseUrl: str
    enabled: bool
    priority: int
    rateLimit: ProviderRateLimit
    createdAt: str
    updatedAt: str

class ConnectionTestResult(BaseModel):
    success: bool
    latencyMs: int
    message: str | None = None
    error: str | None = None
    details: dict

class OptionsChainContract(BaseModel):
    """Single option contract with Greeks."""
    contractSymbol: str
    strike: float
    expiration: str
    optionType: str
    bid: float
    ask: float
    last: float
    volume: int
    openInterest: int
    impliedVolatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    inTheMoney: bool

class OptionsChainResponse(BaseModel):
    """Full options chain for a ticker."""
    ticker: str
    underlyingPrice: float
    expirationDates: list[str]
    contracts: list[OptionsChainContract]
    lastUpdated: str
    dataDelayMinutes: int

class ScanFilters(BaseModel):
    """Query params for GET /api/scan advanced filtering."""
    delta_min: float | None = Field(None, ge=-1.0, le=1.0)
    delta_max: float | None = Field(None, ge=-1.0, le=1.0)
    dte_min: int | None = Field(None, ge=0, le=365)
    dte_max: int | None = Field(None, ge=0, le=365)
    iv_min: float | None = Field(None, ge=0, le=100)
    iv_max: float | None = Field(None, ge=0, le=100)
    vol_oi_min: float | None = Field(None, ge=0, le=10)
    vol_oi_max: float | None = Field(None, ge=0, le=10)
    theta_min: float | None = Field(None, ge=-5.0, le=0.0)
    theta_max: float | None = Field(None, ge=-5.0, le=0.0)
    vega_min: float | None = Field(None, ge=0, le=2.0)
    vega_max: float | None = Field(None, ge=0, le=2.0)
    option_type: str = Field("all", regex="^(call|put|all)$")
    moneyness: str = Field("all", regex="^(itm|otm|atm|all)$")
    min_volume: int | None = Field(None, ge=0)
```

**File**: `app/schemas.py` (extend)

**New Request Schemas**:
```python
class CreateProviderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: ProviderType
    apiKey: str | None = None
    apiSecret: str | None = None
    baseUrl: str = Field(..., min_length=1, max_length=255)
    priority: int = Field(..., gt=0)
    rateLimit: ProviderRateLimit

    @field_validator("baseUrl")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("baseUrl must start with http:// or https://")
        return v

class UpdateProviderRequest(BaseModel):
    """Partial update — all fields optional."""
    name: str | None = Field(None, min_length=1, max_length=100)
    enabled: bool | None = None
    priority: int | None = Field(None, gt=0)
    rateLimit: ProviderRateLimit | None = None

class TestConnectionRequest(BaseModel):
    """Optional body for testing unsaved providers."""
    type: ProviderType
    apiKey: str | None = None
    apiSecret: str | None = None
    baseUrl: str
```

**Tests**: Pydantic validation tests in existing `tests/unit/test_schemas.py`

---

### Task 2.6: Provider Factory & External Adapters (1.5 days)

**File**: `app/providers/provider_factory.py`

**Function**: `create_provider_from_config(config: dict) -> MarketDataProvider`

**Logic**:
```python
def create_provider_from_config(config: dict) -> MarketDataProvider:
    """Dynamically instantiate provider based on type."""
    provider_type = config["type"]
    
    if provider_type == "YAHOO_FINANCE":
        return YahooFinanceProvider()
    elif provider_type == "ALPACA":
        return AlpacaProvider(
            api_key=config["api_key"],
            api_secret=config["api_secret"],
            base_url=config["base_url"]
        )
    elif provider_type == "TRADIER":
        return TradierProvider(
            api_key=config["api_key"],
            base_url=config["base_url"]
        )
    elif provider_type == "CUSTOM":
        return CustomProvider(base_url=config["base_url"])
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
```

**New Files**:
- `app/providers/alpaca_provider.py` — Alpaca API adapter
- `app/providers/tradier_provider.py` — Tradier API adapter
- `app/providers/custom_provider.py` — Generic HTTP provider

**Alpaca Provider** (stub for now):
```python
class AlpacaProvider:
    """Alpaca Markets data provider."""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
    
    def get_options_chain(self, symbol: str, expiration: str | None = None) -> list[OptionContract]:
        # TODO: Implement Alpaca API integration
        raise NotImplementedError("Alpaca provider not yet implemented")
    
    def get_quote(self, symbol: str) -> Quote:
        # TODO: Implement Alpaca API integration
        raise NotImplementedError("Alpaca provider not yet implemented")
    
    def is_available(self) -> bool:
        # Test endpoint: GET /v2/account
        try:
            response = requests.get(
                f"{self.base_url}/v2/account",
                headers={"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.api_secret},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
```

**Tests** (`tests/unit/test_provider_factory.py`):
- Factory creates correct provider type
- Error on unknown type
- Provider instantiation with credentials

**Coverage Target**: 90%

---

## Phase 3: Core Features Implementation (7-9 days)

### Task 3.1: Issue #2 — Provider CRUD API (2 days)

**File**: `app/routers/providers.py`

**Endpoints**:
```python
router = APIRouter(prefix="/api/providers", tags=["Providers"])

@router.get("")
async def list_providers(
    enabled_only: bool = Query(False),
    svc: ProviderService = Depends(get_provider_service)
) -> dict:
    """List all configured providers."""
    return {"providers": svc.list_providers(enabled_only=enabled_only)}

@router.post("", status_code=201)
async def create_provider(
    req: CreateProviderRequest,
    svc: ProviderService = Depends(get_provider_service)
) -> Provider:
    """Create a new provider."""
    return svc.create_provider(req.dict())

@router.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    req: UpdateProviderRequest,
    svc: ProviderService = Depends(get_provider_service)
) -> Provider:
    """Update provider configuration."""
    return svc.update_provider(provider_id, req.dict(exclude_unset=True))

@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str,
    svc: ProviderService = Depends(get_provider_service)
) -> None:
    """Delete a provider."""
    svc.delete_provider(provider_id)
```

**Dependency Wiring** (`app/dependencies.py`):
```python
def get_provider_service() -> ProviderService:
    return ProviderService(ProviderRepository())
```

**Integration Tests** (`tests/integration/test_providers_api.py`):
- GET /api/providers returns providers list
- POST /api/providers creates provider (with encrypted API key)
- PUT /api/providers/{id} updates provider (partial update)
- DELETE /api/providers/{id} removes provider
- Error cases: 404 not found, 409 conflict (duplicate name, last provider), 400 validation

**Logging**:
```python
logger.info("Provider created", extra={"provider_id": provider.id, "type": provider.type})
logger.warning("Provider deletion blocked", extra={"reason": "Last enabled provider"})
```

**Register Router** (`app/main.py`):
```python
from .routers import providers
app.include_router(providers.router)
```

**Coverage Target**: 85%

---

### Task 3.2: Issue #3 — Connection Testing API (1.5 days)

**File**: `app/routers/providers.py` (extend)

**Endpoint**:
```python
@router.post("/{provider_id}/test")
async def test_connection(
    provider_id: str,
    req: TestConnectionRequest = None,
    svc: ProviderService = Depends(get_provider_service)
) -> ConnectionTestResult:
    """Test provider connectivity."""
    test_creds = req.dict() if req else None
    return svc.test_connection(provider_id, test_credentials=test_creds)
```

**Integration Tests** (`tests/integration/test_providers_api.py`):
- POST /api/providers/{id}/test with saved provider (use DB credentials)
- POST /api/providers/temp/test with body credentials (unsaved provider)
- Success scenarios (200 OK with latency)
- Failure scenarios (401, timeout, DNS error, network error)
- HTTP mocking with `responses` library

**Logging**:
```python
logger.info(
    "Connection test",
    extra={
        "provider_id": provider_id,
        "success": result.success,
        "latency_ms": result.latencyMs,
        "error": result.error
    }
)
```

**Coverage Target**: 90%

---

### Task 3.3: Issue #4 — Provider Proxy Endpoints (2.5 days)

**File**: `app/services/provider_proxy_service.py` (new)

**Class**: `ProviderProxyService`

**Methods**:
- `fetch_options_chain(provider_id: str, symbol: str, expiration: str = None) -> OptionsChainResponse`
- `fetch_quote(provider_id: str, symbol: str) -> dict`

**Proxy Logic**:
```python
def fetch_options_chain(self, provider_id: str, symbol: str, expiration: str = None) -> dict:
    """
    Fetch options chain through specific provider.
    
    Flow:
    1. Load provider config from DB
    2. Check if enabled (else raise 503)
    3. Check rate limits (else raise 429)
    4. Instantiate provider via factory
    5. Call provider.get_options_chain()
    6. Record call in history table
    7. Return normalized response
    """
    # Implementation
```

**File**: `app/routers/provider_proxy.py` (new)

**Endpoints**:
```python
router = APIRouter(prefix="/api/providers/{provider_id}/proxy", tags=["Provider Proxy"])

@router.get("/options")
async def proxy_options_chain(
    provider_id: str,
    symbol: str = Query(..., min_length=1, max_length=10),
    expiration: str = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    svc: ProviderProxyService = Depends(get_provider_proxy_service)
) -> OptionsChainResponse:
    """Fetch options chain via specific provider."""
    return svc.fetch_options_chain(provider_id, symbol, expiration)

@router.get("/quote")
async def proxy_quote(
    provider_id: str,
    symbol: str = Query(..., min_length=1, max_length=10),
    svc: ProviderProxyService = Depends(get_provider_proxy_service)
) -> dict:
    """Fetch quote via specific provider."""
    return svc.fetch_quote(provider_id, symbol)
```

**Rate Limiting Logic**:
```python
# In ProviderProxyService
def _check_rate_limits(self, provider_id: str) -> None:
    hourly_count = self.repo.get_hourly_call_count(provider_id)
    daily_count = self.repo.get_daily_call_count(provider_id)
    provider = self.repo.get_by_id(provider_id)
    
    if hourly_count >= provider.rate_limit_max_per_hour:
        raise AppError("Rate limit exceeded (hourly)", status_code=429)
    if daily_count >= provider.rate_limit_max_per_day:
        raise AppError("Rate limit exceeded (daily)", status_code=429)
```

**Integration Tests** (`tests/integration/test_provider_proxy_api.py`):
- GET /api/providers/{id}/proxy/options returns options chain
- GET /api/providers/{id}/proxy/quote returns quote
- Error cases: 400 (missing symbol), 404 (invalid provider), 429 (rate limit), 502 (upstream failure), 503 (disabled provider)
- HTTP mocking for external API calls
- Rate limit enforcement

**Logging**:
```python
logger.debug(
    "Proxy request",
    extra={
        "provider_id": provider_id,
        "endpoint": "options",
        "symbol": symbol,
        "latency_ms": latency
    }
)
```

**Register Router** (`app/main.py`):
```python
from .routers import provider_proxy
app.include_router(provider_proxy.router)
```

**Coverage Target**: 85%

---

### Task 3.4: Issue #1 — Options Chain Endpoint (1.5 days)

**File**: `app/services/options_chain_service.py` (new)

**Class**: `OptionsChainService`

**Method**: `get_chain(ticker: str, expiration: str = None) -> OptionsChainResponse`

**Logic**:
```python
def get_chain(self, ticker: str, expiration: str = None) -> OptionsChainResponse:
    """
    Fetch options chain with Greeks computation.
    
    Steps:
    1. Validate ticker (alphanumeric, 1-5 chars)
    2. Check circuit breaker
    3. Fetch underlying quote (for price)
    4. Fetch options chain
    5. For each contract:
        a. Compute Greeks via Black-Scholes
        b. Determine inTheMoney flag
        c. Generate contractSymbol (OCC format)
    6. Get expiration dates
    7. Return OptionsChainResponse
    """
    # Implementation (see earlier plan)
```

**File**: `app/routers/options_chain.py` (new)

**Endpoint**:
```python
router = APIRouter(prefix="/api", tags=["Options Chain"])

@router.get("/options-chain/{ticker}")
async def get_options_chain(
    ticker: str,
    expiration: str = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    svc: OptionsChainService = Depends(get_options_chain_service)
) -> OptionsChainResponse:
    """Fetch options chain for a ticker."""
    return svc.get_chain(ticker.upper(), expiration)
```

**Contract Symbol Generation** (`app/utils/contract_symbol_generator.py`):
```python
def generate_occ_symbol(
    ticker: str,
    expiration: str,  # YYYY-MM-DD
    option_type: str,  # CALL or PUT
    strike: float
) -> str:
    """
    Generate OCC option symbol.
    
    Format: TICKER[YY][MM][DD][C/P][Strike with 8 digits]
    Example: MSFT260220C00400000 (MSFT Feb 20 2026 Call $400.00)
    """
    exp_date = datetime.strptime(expiration, "%Y-%m-%d")
    yy = exp_date.strftime("%y")
    mm = exp_date.strftime("%m")
    dd = exp_date.strftime("%d")
    cp = "C" if option_type.upper() == "CALL" else "P"
    strike_int = int(strike * 1000)  # Convert to thousandths
    strike_str = f"{strike_int:08d}"
    
    return f"{ticker.upper()}{yy}{mm}{dd}{cp}{strike_str}"
```

**Integration Tests** (`tests/integration/test_options_chain_api.py`):
- GET /api/options-chain/{ticker} returns chain with Greeks
- Response schema validation (all 15 contract fields present)
- Greeks computation accuracy (verify delta/gamma/theta/vega)
- contractSymbol format validation (OCC standard)
- inTheMoney flag correctness
- Error cases: 400 (invalid ticker), 502 (provider failure)

**Register Router** (`app/main.py`):
```python
from .routers import options_chain
app.include_router(options_chain.router)
```

**Update Health Endpoint** (`app/routers/health.py`):
```python
# Add to root endpoint routes list
"routes": [
    # ... existing routes
    "GET /api/options-chain/{ticker}",
]
```

**Coverage Target**: 90%

---

### Task 3.5: Issue #5 — Advanced Scan Filters (2 days)

**File**: `app/routers/scan.py` (modify)

**Current Endpoint**:
```python
@router.get("/scan")
def scan(
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    optionType: str | None = Query(default=None, description="CALL or PUT"),
    minConfidence: float = Query(default=0, ge=0, description="Minimum confidence score"),
    minRiskReward: float = Query(default=0, ge=0, description="Minimum risk/reward ratio"),
    sortBy: str = Query(default="confidenceScore", description="Sort field"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """Get scan opportunities (with optional filtering)."""
    return svc.get_opportunities(...)
```

**New Endpoint** (replace above):
```python
@router.get("/scan")
def scan(
    # Existing params (keep for backwards compatibility)
    symbol: str | None = Query(None),
    optionType: str | None = Query(None),
    minConfidence: float = Query(0, ge=0),
    minRiskReward: float = Query(0, ge=0),
    sortBy: str = Query("confidenceScore"),
    limit: int = Query(50, ge=1, le=200),
    
    # NEW: Advanced filter params (Issue #5)
    delta_min: float | None = Query(None, ge=-1.0, le=1.0),
    delta_max: float | None = Query(None, ge=-1.0, le=1.0),
    dte_min: int | None = Query(None, ge=0, le=365),
    dte_max: int | None = Query(None, ge=0, le=365),
    iv_min: float | None = Query(None, ge=0, le=100),
    iv_max: float | None = Query(None, ge=0, le=100),
    vol_oi_min: float | None = Query(None, ge=0, le=10),
    vol_oi_max: float | None = Query(None, ge=0, le=10),
    theta_min: float | None = Query(None, ge=-5.0, le=0.0),
    theta_max: float | None = Query(None, ge=-5.0, le=0.0),
    vega_min: float | None = Query(None, ge=0, le=2.0),
    vega_max: float | None = Query(None, ge=0, le=2.0),
    option_type_filter: str = Query("all", regex="^(call|put|all)$"),
    moneyness: str = Query("all", regex="^(itm|otm|atm|all)$"),
    min_volume: int | None = Query(None, ge=0),
    
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """Get scan opportunities with advanced filtering."""
    
    # Build filters dict
    filters = ScanFilters(
        delta_min=delta_min,
        delta_max=delta_max,
        dte_min=dte_min,
        dte_max=dte_max,
        # ... all params
    )
    
    return svc.get_opportunities_with_filters(
        symbol=symbol,
        option_type=optionType or option_type_filter,
        min_confidence=minConfidence,
        min_risk_reward=minRiskReward,
        filters=filters,
        sort_by=sortBy,
        limit=limit,
    )
```

**File**: `app/services/scan_service.py` (modify)

**New Method**: `get_opportunities_with_filters()`

**Filtering Logic**:
```python
def get_opportunities_with_filters(
    self,
    symbol: str | None = None,
    option_type: str | None = None,
    min_confidence: float = 0,
    min_risk_reward: float = 0,
    filters: ScanFilters | None = None,
    sort_by: str = "confidenceScore",
    limit: int = 50,
) -> dict:
    """
    Get scan results with advanced filtering.
    
    Apply filters in-memory after fetching from repository.
    """
    # 1. Get all opportunities from DB
    all_opps = self._repo.get_latest(
        symbol=symbol,
        option_type=option_type,
        min_confidence=min_confidence,
        min_risk_reward=min_risk_reward,
        sort_by=sort_by,
        limit=500  # Fetch more, filter client-side
    )
    
    if not filters:
        return {"status": "ok", "opportunities": all_opps[:limit]}
    
    # 2. Apply advanced filters
    filtered = []
    for opp in all_opps:
        # Range filters
        if filters.delta_min is not None and opp.greeks.delta < filters.delta_min:
            continue
        if filters.delta_max is not None and opp.greeks.delta > filters.delta_max:
            continue
        
        # DTE filter (compute from expirationDate)
        dte = (datetime.strptime(opp.expirationDate, "%Y-%m-%d") - datetime.now()).days
        if filters.dte_min is not None and dte < filters.dte_min:
            continue
        if filters.dte_max is not None and dte > filters.dte_max:
            continue
        
        # Volume/OI filter
        if opp.openInterest > 0:
            vol_oi_ratio = opp.volume / opp.openInterest
            if filters.vol_oi_min is not None and vol_oi_ratio < filters.vol_oi_min:
                continue
            if filters.vol_oi_max is not None and vol_oi_ratio > filters.vol_oi_max:
                continue
        
        # Option type filter
        if filters.option_type != "all":
            if opp.optionType.lower() != filters.option_type:
                continue
        
        # Moneyness filter
        if filters.moneyness != "all":
            is_itm = (opp.optionType == "CALL" and opp.underlyingPrice > opp.strikePrice) or \
                     (opp.optionType == "PUT" and opp.underlyingPrice < opp.strikePrice)
            is_otm = not is_itm
            is_atm = abs(opp.underlyingPrice - opp.strikePrice) / opp.strikePrice < 0.02
            
            if filters.moneyness == "itm" and not is_itm:
                continue
            if filters.moneyness == "otm" and not is_otm:
                continue
            if filters.moneyness == "atm" and not is_atm:
                continue
        
        # Volume threshold
        if filters.min_volume is not None and opp.volume < filters.min_volume:
            continue
        
        # All filters passed
        filtered.append(opp)
    
    # 3. Sort and limit
    return {"status": "ok", "opportunities": filtered[:limit], "totalFiltered": len(filtered)}
```

**Integration Tests** (`tests/integration/test_scan_api.py`):
- GET /api/scan with no params (backwards compatible)
- GET /api/scan with delta_min/delta_max filters
- GET /api/scan with DTE filters
- GET /api/scan with volume/OI filters
- GET /api/scan with combined filters (delta + DTE + option_type)
- Empty results when filters too narrow
- Invalid param values return 422

**Unit Tests** (`tests/unit/test_scan_service.py`):
- Filter logic correctness (each filter type)
- Moneyness calculation (ITM/OTM/ATM)
- Volume/OI ratio calculation
- DTE computation from expiration date

**Logging**:
```python
logger.debug(
    "Scan with filters",
    extra={
        "filters_applied": filters.dict(exclude_unset=True),
        "total_before_filter": len(all_opps),
        "total_after_filter": len(filtered)
    }
)
```

**Coverage Target**: 95%

---

## Phase 4: Integration & Testing (3-4 days)

### Task 4.1: End-to-End Integration Tests (2 days)

**File**: `tests/integration/test_full_workflow.py`

**Scenarios**:
1. **Provider Setup Workflow**:
   - Create Alpaca provider → Test connection → Enable → Delete Yahoo provider → Verify failover

2. **Options Chain Workflow**:
   - GET /api/options-chain/MSFT → Verify Greeks → Verify contract symbols → Check response time <2s

3. **Scan with Filters Workflow**:
   - Run scan → Apply delta filters → Verify results match criteria → Sort by confidence

4. **Proxy Workflow**:
   - Create provider → Proxy options chain → Compare with direct endpoint → Verify rate limiting

5. **Error Handling**:
   - Invalid ticker → 400
   - Disabled provider → 503
   - Rate limit exceeded → 429
   - Upstream failure → 502

**Coverage Target**: 100% of happy paths + major error paths

---

### Task 4.2: Load & Performance Testing (1 day)

**Tool**: `locust` or `pytest-benchmark`

**Scenarios**:
- 100 concurrent users hitting GET /api/scan with filters
- 50 concurrent provider proxy requests
- 20 concurrent options chain requests

**Performance Targets**:
| Endpoint | Target Latency | Max Latency |
|----------|----------------|-------------|
| GET /api/scan (no filters) | <500ms | <1s |
| GET /api/scan (with filters) | <1s | <2s |
| GET /api/options-chain/{ticker} | <2s | <5s |
| POST /api/providers | <200ms | <500ms |
| POST /api/providers/{id}/test | <10s | <10s |
| GET /api/providers/{id}/proxy/options | <3s | <8s |

---

### Task 4.3: Security Audit (1 day)

**Checklist**:
- [ ] No API keys in logs
- [ ] Encryption keys in Azure Key Vault (not env vars)
- [ ] SQL injection tests (parameterized queries verified)
- [ ] Rate limiting tested (verify 429 responses)
- [ ] Input validation for all endpoints (fuzz testing)
- [ ] CORS headers correct
- [ ] API key auth middleware enabled in production

**Tools**:
- `bandit app/` — Python security linter
- `safety check` — Dependency vulnerability scanner
- Manual penetration testing with `curl`

---

## Phase 5: Documentation & Deployment (2-3 days)

### Task 5.1: OpenAPI Spec Validation (0.5 days)

**Verify**:
- All new endpoints appear in `/openapi.json`
- Request/response schemas documented
- Error responses documented (400, 404, 409, 429, 502, 503)

**Tool**: Swagger UI at `/docs`

---

### Task 5.2: README & Migration Guide (0.5 days)

**File**: `README.md` (update)

**Sections to Add**:
```markdown
## Environment Variables

### Encryption (Required)
- `ENCRYPTION_KEY` — Fernet encryption key for provider API keys (32-byte base64)

### Provider Configuration
- `MARKET_DATA_PROVIDER` — Default provider (`yahoo_finance`, `alpaca`, `tradier`, `custom`)

## Migrations

Run all pending migrations:
```bash
# Apply schema changes
python scripts/run_migrations.py
```

## New Endpoints (v3.1.0)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/providers` | GET | List all providers |
| `/api/providers` | POST | Create provider |
| `/api/providers/{id}` | PUT | Update provider |
| `/api/providers/{id}` | DELETE | Delete provider |
| `/api/providers/{id}/test` | POST | Test connection |
| `/api/providers/{id}/proxy/options` | GET | Proxy options chain |
| `/api/providers/{id}/proxy/quote` | GET | Proxy quote |
| `/api/options-chain/{ticker}` | GET | Get options chain |
| `/api/scan?delta_min=X&...` | GET | Scan with filters |
```

**File**: `docs/MIGRATION_v3.1.md` (create)

**Content**: Step-by-step guide for upgrading from v3.0 → v3.1

---

### Task 5.3: Deployment to Azure (1 day)

**Pre-Deployment Checklist**:
- [ ] All tests pass (327 → 450+ tests)
- [ ] Coverage ≥85%
- [ ] No deprecation warnings
- [ ] Environment variables set in Azure App Service
- [ ] Encryption key in Azure Key Vault
- [ ] Database migrations run

**Deployment Steps**:
1. Run migrations against production Azure SQL
2. Set `ENCRYPTION_KEY` in Azure App Service config
3. Deploy via GitHub Actions (existing pipeline)
4. Smoke test all new endpoints
5. Monitor Application Insights for errors

**Rollback Plan**: Revert to v3.0 Docker image + rollback migration

---

### Task 5.4: Frontend Coordination (1 day)

**Notify frontend team**:
- Backend endpoints ready
- OpenAPI spec URL
- Sample requests/responses
- Rate limit headers format

**Coordinate testing**:
- End-to-end test with frontend dev environment
- Verify failover mechanism works
- Verify advanced filters work
- Verify options chain loads without 404

---

## Implementation Timeline

### Week 1: Foundation
- **Day 1-2**: Architecture planning + database schema + migrations
- **Day 3**: Encryption utility + provider repository
- **Day 4-5**: Provider service + connection testing logic

### Week 2: Core Features (P0)
- **Day 6-7**: Issue #2 (Provider CRUD API)
- **Day 8**: Issue #3 (Connection Testing API)
- **Day 9-10**: Issue #4 (Provider Proxy — partial)

### Week 3: Core Features (P1) + Bug
- **Day 11**: Issue #4 (Provider Proxy — complete)
- **Day 12-13**: Issue #1 (Options Chain Endpoint)
- **Day 14-15**: Issue #5 (Advanced Scan Filters)

### Week 4: Testing & Deployment
- **Day 16-17**: Integration tests + load testing
- **Day 18**: Security audit
- **Day 19-20**: Documentation + deployment
- **Day 21**: Frontend coordination + fixes

**Total**: 21 working days (~4 weeks)

---

## Risk Assessment

### High Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Encryption key leak | Low | **Critical** | Use Azure Key Vault, never commit to Git |
| Database migration failure | Medium | **High** | Test in dev first, have rollback scripts |
| External API downtime (Alpaca/Tradier) | Medium | Medium | Implement circuit breaker, failover to Yahoo |
| Performance degradation (scan filters) | Medium | Medium | Cache scan results, optimize SQL queries |

### Medium Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Provider API rate limits | High | Medium | Track call counts, enforce limits, show warnings |
| Frontend-backend schema mismatch | Medium | Medium | Share OpenAPI spec, coordinate testing |
| Test coverage gaps | Low | Medium | Enforce 85% coverage gate in CI/CD |

---

## Success Criteria

### Functional
- [ ] All 5 GitHub issues closed with "Completed" status
- [ ] All acceptance criteria met for each issue
- [ ] Frontend successfully integrates with all new endpoints
- [ ] Zero regressions (all existing 327 tests still pass)

### Non-Functional
- [ ] Test coverage ≥85% (100+ new tests)
- [ ] All endpoints respond <5s (p99 latency)
- [ ] Zero security vulnerabilities (`bandit`, `safety check`)
- [ ] Zero critical errors in Application Insights (first 48h post-deploy)

### Documentation
- [ ] OpenAPI spec complete and accurate
- [ ] README updated with env vars and new endpoints
- [ ] Migration guide written
- [ ] Code review completed (all PRs approved)

---

## Post-Implementation

### Monitoring (First 2 Weeks)
- **Application Insights**: Watch for errors, latency spikes
- **Rate Limits**: Monitor provider call counts
- **Circuit Breaker**: Log when providers go into cooldown
- **User Feedback**: Track frontend issues related to new endpoints

### Future Enhancements
- **Issue #2 Extension**: Provider scheduling (enable/disable at specific times)
- **Issue #4 Extension**: Smart failover (auto-switch on 3 consecutive failures)
- **Issue #5 Extension**: Save filter presets to database
- **New Feature**: Webhook notifications when rate limits near threshold

---

**End of Implementation Plan**

---

## Appendix A: Test Case Summary

| Component | Unit Tests | Integration Tests | Total |
|-----------|------------|-------------------|-------|
| Encryption | 10 | 0 | 10 |
| Provider Repository | 15 | 5 | 20 |
| Provider Service | 20 | 8 | 28 |
| Proxy Service | 18 | 10 | 28 |
| Options Chain Service | 12 | 5 | 17 |
| Scan Filters | 25 | 8 | 33 |
| Provider Factory | 5 | 0 | 5 |
| Contract Symbol Generator | 8 | 0 | 8 |
| Provider CRUD API | 0 | 12 | 12 |
| Connection Testing API | 0 | 8 | 8 |
| Provider Proxy API | 0 | 10 | 10 |
| Options Chain API | 0 | 5 | 5 |
| Scan API (filters) | 0 | 8 | 8 |
| Full Workflow | 0 | 10 | 10 |
| **Total** | **113** | **89** | **202** |

**Grand Total (Existing + New)**: 327 + 202 = **529 tests**

---

## Appendix B: File Creation Checklist

### New Files (27)
- [ ] `migrations/004_create_providers.sql`
- [ ] `migrations/005_create_provider_call_history.sql`
- [ ] `app/utils/encryption.py`
- [ ] `app/utils/contract_symbol_generator.py`
- [ ] `app/repositories/provider_repository.py`
- [ ] `app/services/provider_service.py`
- [ ] `app/services/provider_proxy_service.py`
- [ ] `app/services/options_chain_service.py`
- [ ] `app/providers/provider_factory.py`
- [ ] `app/providers/alpaca_provider.py`
- [ ] `app/providers/tradier_provider.py`
- [ ] `app/providers/custom_provider.py`
- [ ] `app/routers/providers.py`
- [ ] `app/routers/provider_proxy.py`
- [ ] `app/routers/options_chain.py`
- [ ] `tests/unit/test_encryption.py`
- [ ] `tests/unit/test_provider_repository.py`
- [ ] `tests/unit/test_provider_service.py`
- [ ] `tests/unit/test_provider_proxy_service.py`
- [ ] `tests/unit/test_options_chain_service.py`
- [ ] `tests/unit/test_provider_factory.py`
- [ ] `tests/unit/test_contract_symbol_generator.py`
- [ ] `tests/integration/test_providers_api.py`
- [ ] `tests/integration/test_provider_proxy_api.py`
- [ ] `tests/integration/test_options_chain_api.py`
- [ ] `tests/integration/test_full_workflow.py`
- [ ] `docs/MIGRATION_v3.1.md`

### Modified Files (9)
- [ ] `app/models.py` (add 8 new models)
- [ ] `app/schemas.py` (add 3 request schemas)
- [ ] `app/providers/base.py` (add `get_expiration_dates()` method)
- [ ] `app/providers/yahoo_provider.py` (implement `get_expiration_dates()`)
- [ ] `app/providers/mock_provider.py` (implement `get_expiration_dates()`)
- [ ] `app/dependencies.py` (add 3 new service factories)
- [ ] `app/routers/scan.py` (add 13 new query params)
- [ ] `app/services/scan_service.py` (add `get_opportunities_with_filters()`)
- [ ] `app/main.py` (register 3 new routers)
- [ ] `app/routers/health.py` (add new route to listing)
- [ ] `README.md` (document new env vars + endpoints)
- [ ] `requirements.txt` (add `cryptography`, possibly `requests`)
- [ ] `tests/conftest.py` (add provider service mocks)

---

**Version**: 1.0  
**Prepared by**: AI Product Manager  
**Review Date**: February 15, 2026
