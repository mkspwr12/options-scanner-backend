-- Migration 008: Create positions table for portfolio positions
-- Idempotent: safe to re-run
-- Issue #18: POST /api/portfolio/add-position

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'positions')
BEGIN
    CREATE TABLE positions (
        id                VARCHAR(50)    NOT NULL PRIMARY KEY,
        symbol            VARCHAR(10)    NOT NULL,
        strike            DECIMAL(12,2)  NOT NULL,
        expiration        DATE           NOT NULL,
        option_type       VARCHAR(4)     NOT NULL,  -- call or put
        quantity          INT            NOT NULL,
        premium           DECIMAL(12,4)  NOT NULL,
        entry_date        DATE           NOT NULL,
        current_value     DECIMAL(14,2)  NOT NULL DEFAULT 0,
        pnl               DECIMAL(14,2)  NOT NULL DEFAULT 0,
        status            VARCHAR(10)    NOT NULL DEFAULT 'open',  -- open or closed
        created_at        DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        updated_at        DATETIME2      NOT NULL DEFAULT GETUTCDATE()
    );

    PRINT 'Created table: positions';
END
ELSE
    PRINT 'Table positions already exists — skipping';
GO

-- Indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_positions_symbol' AND object_id = OBJECT_ID('positions'))
BEGIN
    CREATE INDEX ix_positions_symbol ON positions (symbol);
    PRINT 'Created index: ix_positions_symbol';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_positions_status' AND object_id = OBJECT_ID('positions'))
BEGIN
    CREATE INDEX ix_positions_status ON positions (status);
    PRINT 'Created index: ix_positions_status';
END
GO
