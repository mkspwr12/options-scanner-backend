-- Migration 003: Create scan_results table
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scan_results')
BEGIN
    CREATE TABLE scan_results (
        id                  VARCHAR(50)    NOT NULL PRIMARY KEY,
        symbol              VARCHAR(10)    NOT NULL,
        strike_price        DECIMAL(12,2)  NOT NULL,
        expiration_date     DATE           NOT NULL,
        option_type         VARCHAR(4)     NOT NULL,
        current_price       DECIMAL(12,4)  NULL,
        underlying_price    DECIMAL(12,2)  NULL,
        implied_volatility  DECIMAL(8,4)   NULL,
        delta               DECIMAL(8,4)   NULL,
        gamma               DECIMAL(8,4)   NULL,
        theta               DECIMAL(8,4)   NULL,
        vega                DECIMAL(8,4)   NULL,
        potential_gain      DECIMAL(12,4)  NULL,
        potential_loss       DECIMAL(12,4)  NULL,
        risk_reward_ratio   DECIMAL(8,4)   NULL,
        confidence_score    DECIMAL(5,2)   NULL,
        strategy_type       VARCHAR(30)    NULL,  -- NULL for single-leg
        scan_timestamp      BIGINT         NOT NULL,
        created_at          DATETIME2      NOT NULL DEFAULT GETUTCDATE()
    );

    PRINT 'Created table: scan_results';
END
ELSE
    PRINT 'Table scan_results already exists — skipping';
GO

-- Indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_symbol' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_symbol ON scan_results (symbol);
    PRINT 'Created index: ix_scan_symbol';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_timestamp' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_timestamp ON scan_results (scan_timestamp DESC);
    PRINT 'Created index: ix_scan_timestamp';
END
GO
