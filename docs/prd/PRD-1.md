# PRD: Options Scanner Backend — Stability & Feature Enhancement

**Epic**: #1  
**Status**: Draft  
**Author**: Product Manager Agent  
**Date**: 2026-02-14  
**Stakeholders**: Developer / Owner  
**Priority**: p0

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Target Users](#2-target-users)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Requirements](#4-requirements)
5. [User Stories & Features](#5-user-stories--features)
6. [User Flows](#6-user-flows)
7. [Dependencies & Constraints](#7-dependencies--constraints)
8. [Risks & Mitigations](#8-risks--mitigations)
9. [Timeline & Milestones](#9-timeline--milestones)
10. [Out of Scope](#10-out-of-scope)
11. [Open Questions](#11-open-questions)

---

## 1. Problem Statement

### What problem are we solving?

The Options Scanner Backend is currently a **prototype/scaffold** — it serves hardcoded sample data, has no data persistence layer, no real market data integration, no authentication, no input validation, and no test coverage. It cannot be used as a real trading tool in its current state.

### Why is this important?

Without real data, persistence, and stability improvements, the application provides no actual value to options traders. Users cannot scan real opportunities, track real trades, or trust the system for reliable portfolio management.

### What happens if we don't solve this?

The backend remains a static demo. No real users can benefit from it, and the codebase will accumulate technical debt as frontend features are built against fake data contracts.

### Current State Assessment

| Area | Current State | Target State |
|------|--------------|--------------|
| **Market Data** | Hardcoded sample data in `/api/scan` | Live options chain data from a market data provider |
| **Trade Tracking** | Endpoints accept data but don't persist | Full CRUD with Azure SQL persistence |
| **Watchlist** | Static list `["META", "SPY", "AAPL", "NVDA"]` | User-specific persisted watchlist |
| **Portfolio** | Hardcoded metrics and trades | Calculated from real tracked trades |
| **Database** | `db.py` exists but `get_connection()` is unused by any endpoint | All CRUD endpoints use Azure SQL |
| **Input Validation** | Endpoints accept `Dict[str, Any]` — no validation | Typed Pydantic request models |
| **Error Handling** | Bare `except Exception` everywhere | Structured error responses with proper HTTP codes |
| **Testing** | 0% coverage — no test files | ≥80% coverage with unit + integration tests |
| **Auth** | None | API key or JWT authentication |
| **Config** | Hardcoded CORS origins, env vars only | Configurable, environment-aware settings |
| **Observability** | In-memory `LogStore` only | Structured logging + Azure Monitor traces |

---

## 2. Target Users

### Primary Users

**User Persona 1: Active Options Trader**
- **Demographics**: 25-55, technically comfortable, uses multiple platforms
- **Goals**: Scan for high-probability option trades, track positions, monitor portfolio Greeks
- **Pain Points**: Too many tickers to manually analyze; wants automated scanning with Greeks-based filtering
- **Behaviors**: Checks markets daily, manages 5-20 open positions at a time

### Secondary Users

**Developer / Maintainer**: Needs clean, testable, well-documented code to iterate on features safely.

---

## 3. Goals & Success Metrics

### Business Goals

1. **Real Data Integration**: Connect to a live market data provider so scans return actionable data
2. **Persistence**: All trades, watchlists, and portfolio state survive server restarts
3. **Stability**: Structured error handling, input validation, and ≥80% test coverage
4. **Production-Readiness**: Authentication, rate limiting, proper configuration management

### Success Metrics (KPIs)

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Test coverage | 0% | ≥80% | Phase 1 |
| Endpoints with typed request models | 0/5 POST | 5/5 | Phase 1 |
| Active data persistence | 0 tables | 3+ tables (trades, watchlist, scans) | Phase 1 |
| Market data integration | None | 1 provider connected | Phase 2 |
| API uptime (measured via health check) | Unknown | 99.5% | Phase 3 |
| Mean error response time | N/A | < 200ms | Phase 2 |

---

## 4. Requirements

### 4.1 Functional Requirements

#### Must Have (P0) — Stability & Persistence

1. **Database Schema & Migrations**
   - **User Story**: As a developer, I want database tables for trades, watchlist, and scan history so that data persists across restarts.
   - **Acceptance Criteria**:
     - [ ] SQL migration scripts create `trades`, `watchlist_items`, `scan_results` tables
     - [ ] Schema supports all fields in existing Pydantic models
     - [ ] Migration is idempotent (safe to re-run)

2. **Trade Persistence (CRUD)**
   - **User Story**: As a trader, I want my tracked trades saved to the database so I don't lose them on restart.
   - **Acceptance Criteria**:
     - [ ] `POST /api/trades/track` inserts into `trades` table
     - [ ] `POST /api/trades/close` updates trade with exit data and sets `status=closed`
     - [ ] `GET /api/portfolio` reads real data from `trades` table
     - [ ] Portfolio metrics are calculated from actual trade records

3. **Watchlist Persistence**
   - **User Story**: As a trader, I want my watchlist saved so it remains after I close the app.
   - **Acceptance Criteria**:
     - [ ] `POST /api/watchlist/add` inserts symbol into `watchlist_items` table
     - [ ] `POST /api/watchlist/remove` deletes symbol from `watchlist_items` table
     - [ ] `GET /api/watchlist` returns symbols from database

4. **Input Validation & Typed Request Models**
   - **User Story**: As a developer, I want all POST endpoints to use Pydantic request models so that invalid data is rejected before processing.
   - **Acceptance Criteria**:
     - [ ] `POST /api/trades/track` uses `TrackTradeRequest` model (not `Dict[str, Any]`)
     - [ ] `POST /api/trades/close` uses `CloseTradeRequest` model
     - [ ] `POST /api/watchlist/add` uses `WatchlistRequest` model
     - [ ] `POST /api/watchlist/remove` uses `WatchlistRequest` model
     - [ ] `POST /api/logs` uses `LogEntryRequest` model
     - [ ] Invalid requests return 422 with descriptive errors

5. **Structured Error Handling**
   - **User Story**: As a frontend developer, I want consistent error responses so I can display meaningful messages.
   - **Acceptance Criteria**:
     - [ ] Global exception handler returns `{"status": "error", "detail": "...", "code": <int>}`
     - [ ] No bare `except Exception: pass` patterns in production code
     - [ ] Database connection errors return 503
     - [ ] Validation errors return 422
     - [ ] Not-found errors return 404

6. **Test Suite Foundation**
   - **User Story**: As a developer, I want unit and integration tests so that changes don't introduce regressions.
   - **Acceptance Criteria**:
     - [ ] `pytest` configured with `conftest.py`
     - [ ] Unit tests for all models and config
     - [ ] Integration tests for all API endpoints using `TestClient`
     - [ ] Test coverage ≥80%
     - [ ] Tests runnable with `pytest` from project root

#### Should Have (P1) — Feature Enhancement

7. **Real Market Data Integration**
   - **User Story**: As a trader, I want `/api/scan` to return real options data so I can make informed trades.
   - **Acceptance Criteria**:
     - [ ] Integrate with a market data provider (e.g., Yahoo Finance, Tradier, Polygon.io, or CBOE)
     - [ ] Fetch live options chains for watchlist symbols
     - [ ] Calculate Greeks (delta, gamma, theta, vega) from live IV data
     - [ ] Score opportunities using risk/reward analysis
     - [ ] Fallback to cached data if provider is unavailable (circuit breaker)

8. **Background Scan Scheduler**
   - **User Story**: As a trader, I want the scanner to run automatically on a schedule so I get fresh opportunities without manual refresh.
   - **Acceptance Criteria**:
     - [ ] Background task runs scan every N minutes (configurable)
     - [ ] Scan results stored in `scan_results` table
     - [ ] `/api/scan` returns latest stored results (not computed on-demand)
     - [ ] Scan can be triggered manually via `POST /api/scan/trigger`

9. **API Authentication**
   - **User Story**: As a system owner, I want API endpoints protected so only authorized users can access data.
   - **Acceptance Criteria**:
     - [ ] API key authentication via `X-API-Key` header
     - [ ] Health endpoints (`/healthz`, `/health`) remain unauthenticated
     - [ ] Unauthorized requests return 401
     - [ ] API key configurable via environment variable

10. **Configuration Enhancement**
    - **User Story**: As a developer, I want a clean configuration system that supports multiple environments.
    - **Acceptance Criteria**:
      - [ ] CORS origins configurable via `ALLOWED_ORIGINS` env var
      - [ ] Scan interval, log retention, and feature flags configurable
      - [ ] `.env.example` documents all available settings
      - [ ] `Settings` dataclass includes all configurable values

#### Could Have (P2)

11. **Rate Limiting**
    - **User Story**: As a system owner, I want rate limiting to protect against abuse.
    - **Acceptance Criteria**:
      - [ ] Rate limit of 60 requests/minute per API key
      - [ ] 429 response with `Retry-After` header when exceeded

12. **Scan Filtering & Sorting**
    - **User Story**: As a trader, I want to filter scan results by symbol, option type, confidence score, etc.
    - **Acceptance Criteria**:
      - [ ] Query parameters: `symbol`, `optionType`, `minConfidence`, `minRiskReward`
      - [ ] Sort by `confidenceScore`, `riskRewardRatio`, `potentialGain`

#### Won't Have (Out of Scope for This Epic)

- Real-time WebSocket streaming of price updates
- Multi-user support with user accounts
- Frontend changes (this epic is backend-only)
- Mobile-specific API endpoints
- Options order execution (placing trades via broker API)

### 4.2 AI/ML Requirements

#### Technology Classification
- [x] **Rule-based / statistical** — no model needed (deterministic logic only)

> Options scanning uses quantitative models (Black-Scholes, Greeks calculation) which are mathematical, not ML. AI/ML may be added in a future epic for predictive scoring.

### 4.3 Non-Functional Requirements

#### Performance
- **Response Time**: API responses < 500ms (p95), scan endpoint < 2s
- **Throughput**: Handle 50 concurrent requests
- **Uptime**: 99.5% availability

#### Security
- **Authentication**: API key (P1), JWT in future
- **Data Protection**: SQL parameterized queries (already via pyodbc), TLS in transit (Azure default)
- **No Hardcoded Secrets**: All credentials via env vars or Managed Identity

#### Scalability
- **Concurrent Users**: Support 50 concurrent users
- **Data Volume**: Store up to 1 year of scan history and trades

#### Reliability
- **Error Handling**: Structured error responses, circuit breakers for external APIs
- **Recovery**: Auto-retry on transient DB connection failures (up to 3 retries)
- **Monitoring**: Azure Application Insights (already partially integrated)

---

## 5. User Stories & Features

### Feature 1: Database Persistence Layer
**Description**: Create SQL schema and migrate all endpoints from hardcoded data to database persistence  
**Priority**: P0  
**Epic**: #1

| Story ID | As a... | I want... | So that... | Priority | Estimate |
|----------|---------|-----------|------------|----------|----------|
| US-1.1 | developer | database migration scripts | tables are created safely | P0 | 1 day |
| US-1.2 | trader | trade tracking to persist | my trades survive restarts | P0 | 2 days |
| US-1.3 | trader | watchlist to persist | my watchlist is saved | P0 | 1 day |
| US-1.4 | trader | portfolio from real data | I see accurate P/L | P0 | 2 days |

### Feature 2: Input Validation & Error Handling
**Description**: Replace `Dict[str, Any]` with typed Pydantic models; add structured error handling  
**Priority**: P0  
**Epic**: #1

| Story ID | As a... | I want... | So that... | Priority | Estimate |
|----------|---------|-----------|------------|----------|----------|
| US-2.1 | developer | typed request models | invalid data is rejected | P0 | 1 day |
| US-2.2 | frontend dev | consistent error format | I can display errors reliably | P0 | 1 day |

### Feature 3: Test Suite
**Description**: Add pytest configuration and comprehensive tests  
**Priority**: P0  
**Epic**: #1

| Story ID | As a... | I want... | So that... | Priority | Estimate |
|----------|---------|-----------|------------|----------|----------|
| US-3.1 | developer | unit tests for models/config | I catch regressions | P0 | 1 day |
| US-3.2 | developer | integration tests for endpoints | API behavior is verified | P0 | 2 days |

### Feature 4: Market Data Integration
**Description**: Connect to a real market data provider for live options chains  
**Priority**: P1  
**Epic**: #1

| Story ID | As a... | I want... | So that... | Priority | Estimate |
|----------|---------|-----------|------------|----------|----------|
| US-4.1 | trader | real options data in scans | I can make informed trades | P1 | 3 days |
| US-4.2 | trader | background scan scheduler | I get fresh data automatically | P1 | 2 days |

### Feature 5: Authentication & Configuration
**Description**: API key auth and configurable settings  
**Priority**: P1  
**Epic**: #1

| Story ID | As a... | I want... | So that... | Priority | Estimate |
|----------|---------|-----------|------------|----------|----------|
| US-5.1 | system owner | API key authentication | only authorized users access data | P1 | 1 day |
| US-5.2 | developer | configurable CORS/settings | I can deploy to any environment | P1 | 1 day |

---

## 6. User Flows

### Primary Flow: Scan & Track Trade

**Trigger**: User opens the app and views scan results  
**Preconditions**: Backend is running, database is migrated, market data provider configured

**Steps**:
1. User visits the scanner page → Frontend calls `GET /api/scan`
2. Backend fetches latest scan results from DB (or triggers live scan if stale)
3. User reviews opportunities sorted by confidence score
4. User clicks "Track" on a trade → Frontend calls `POST /api/trades/track`
5. Backend validates input, saves trade to `trades` table, returns trade ID
6. User views portfolio → Frontend calls `GET /api/portfolio`
7. Backend calculates metrics from all trades in DB, returns portfolio

**Alternative Flows**:
- **6a. Market data unavailable**: Backend returns cached/stale results with `stale: true` flag
- **6b. Invalid trade data**: Backend returns 422 with validation error details

### Secondary Flow: Manage Watchlist

**Trigger**: User adds or removes a symbol from watchlist

**Steps**:
1. User types symbol → Frontend calls `POST /api/watchlist/add` with `{"symbol": "TSLA"}`
2. Backend validates symbol format, inserts into `watchlist_items`, returns success
3. Scanner includes the new symbol in subsequent scans
4. User removes symbol → Frontend calls `POST /api/watchlist/remove`
5. Backend deletes from `watchlist_items`, returns success

---

## 7. Dependencies & Constraints

### Technical Dependencies

| Dependency | Type | Status | Impact if Unavailable |
|------------|------|--------|----------------------|
| Azure SQL Database | Internal | Available | High — no persistence |
| Azure Managed Identity | Internal | Available | High — no DB auth |
| Market Data Provider (TBD) | External | Not Yet Integrated | Medium — scan returns stale/sample data |
| pyodbc + ODBC Driver 18 | Internal | Available | High — DB connection fails |

### Technical Constraints
- Must use existing Azure SQL Database (connection string pattern already established in `db.py`)
- Must maintain backward compatibility with existing frontend API contracts
- Managed Identity authentication for DB (no stored credentials)
- Python 3.11 on Azure App Service (Linux)
- Known pyodbc segfault issue on Linux for certain operations (noted in `/health` endpoint)

---

## 8. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| pyodbc segfault on Linux (noted in codebase) | High | Medium | Test DB operations in Azure staging; consider async DB driver (e.g., `aioodbc`) as fallback |
| Market data provider rate limits | Medium | High | Implement caching, scheduled scans, circuit breaker |
| Breaking frontend API contract | High | Low | Keep response shapes identical; add new fields, don't remove existing ones |
| Azure SQL connection pooling | Medium | Medium | Use connection pooling; don't hold connections open |
| Test flakiness with real DB | Medium | Medium | Use SQLite for unit tests, Azure SQL for integration tests only |

---

## 9. Timeline & Milestones

### Phase 1: Stability Foundation (Week 1-2)
**Goal**: Database persistence, input validation, error handling, tests  
**Deliverables**:
- SQL migration scripts
- Trade & watchlist CRUD with DB persistence
- Typed Pydantic request models for all POST endpoints
- Structured error handling middleware
- pytest suite with ≥80% coverage

**Stories**: US-1.1, US-1.2, US-1.3, US-1.4, US-2.1, US-2.2, US-3.1, US-3.2

### Phase 2: Feature Enhancement (Week 3-4)
**Goal**: Real market data, background scanning, authentication  
**Deliverables**:
- Market data provider integration
- Background scan scheduler
- API key authentication
- Enhanced configuration system

**Stories**: US-4.1, US-4.2, US-5.1, US-5.2

### Phase 3: Hardening (Week 5)
**Goal**: Production readiness  
**Deliverables**:
- Rate limiting
- Scan filtering and sorting
- Performance testing
- Documentation updates

---

## 10. Out of Scope

**Explicitly excluded from this Epic**:
- WebSocket real-time streaming — Deferred to future epic
- Multi-user support / user accounts — Current design is single-user
- Frontend changes — This is backend-only work
- Order execution via broker APIs — Future phase
- AI/ML-based trade recommendations — Future epic after base stability

**Future Considerations**:
- AI-powered confidence scoring (use historical scan accuracy to train a model)
- Multi-broker integration (Schwab, IBKR, Tradier)
- Options chain visualization API improvements

---

## 11. Open Questions

| Question | Owner | Status | Resolution |
|----------|-------|--------|------------|
| Which market data provider to use? (Yahoo Finance free tier, Tradier, Polygon.io) | Developer | Open | Evaluate cost, rate limits, data quality |
| Should we use connection pooling for Azure SQL? | Developer | Open | Test pyodbc behavior on Linux first |
| Is the existing frontend expecting exact response shapes, or can we extend? | Developer | Open | Audit frontend code for API contract |
| Do we need to handle the pyodbc Linux segfault differently? | Developer | Open | Test in staging; consider aioodbc |

---

## Review & Approval

| Stakeholder | Role | Status | Date | Comments |
|-------------|------|--------|------|----------|
| Product Manager Agent | PM | Draft | 2026-02-14 | Initial PRD created |

---

**Generated by AgentX Product Manager Agent**  
**Last Updated**: 2026-02-14  
**Version**: 1.0
