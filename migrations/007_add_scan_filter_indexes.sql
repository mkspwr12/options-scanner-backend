-- Migration 007: Add indexes for advanced scan filters
-- Idempotent: safe to re-run

-- Composite index for Greek-based filtering
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_results_greeks' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_results_greeks
        ON scan_results(delta, gamma, theta, vega);
    PRINT 'Created index: ix_scan_results_greeks';
END
GO

-- Index for IV filtering
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_results_iv' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_results_iv
        ON scan_results(implied_volatility);
    PRINT 'Created index: ix_scan_results_iv';
END
GO

-- Index for expiration-based filtering (DTE calculation)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_results_expiration' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_results_expiration
        ON scan_results(expiration_date);
    PRINT 'Created index: ix_scan_results_expiration';
END
GO

-- Index for confidence + risk-reward (common filter combo)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_scan_results_score_rr' AND object_id = OBJECT_ID('scan_results'))
BEGIN
    CREATE INDEX ix_scan_results_score_rr
        ON scan_results(confidence_score DESC, risk_reward_ratio DESC);
    PRINT 'Created index: ix_scan_results_score_rr';
END
GO
