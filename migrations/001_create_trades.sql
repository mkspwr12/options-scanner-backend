-- Migration 001: Create trades table
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'trades')
BEGIN
    CREATE TABLE trades (
        id                VARCHAR(50)    NOT NULL PRIMARY KEY,
        opportunity_id    VARCHAR(50)    NOT NULL,
        symbol            VARCHAR(10)    NOT NULL,
        strike_price      DECIMAL(12,2)  NOT NULL,
        expiration_date   DATE           NOT NULL,
        option_type       VARCHAR(4)     NOT NULL,  -- CALL or PUT
        entry_price       DECIMAL(12,4)  NOT NULL,
        current_price     DECIMAL(12,4)  NOT NULL,
        exit_price        DECIMAL(12,4)  NULL,
        quantity          INT            NOT NULL,
        underlying_price  DECIMAL(12,2)  NOT NULL,
        delta             DECIMAL(8,4)   NULL,
        gamma             DECIMAL(8,4)   NULL,
        theta             DECIMAL(8,4)   NULL,
        vega              DECIMAL(8,4)   NULL,
        entry_date        BIGINT         NOT NULL,  -- epoch milliseconds
        exit_date         BIGINT         NULL,
        status            VARCHAR(10)    NOT NULL DEFAULT 'active',  -- active or closed
        created_at        DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        updated_at        DATETIME2      NOT NULL DEFAULT GETUTCDATE()
    );

    PRINT 'Created table: trades';
END
ELSE
    PRINT 'Table trades already exists — skipping';
GO

-- Indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_trades_symbol' AND object_id = OBJECT_ID('trades'))
BEGIN
    CREATE INDEX ix_trades_symbol ON trades (symbol);
    PRINT 'Created index: ix_trades_symbol';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_trades_status' AND object_id = OBJECT_ID('trades'))
BEGIN
    CREATE INDEX ix_trades_status ON trades (status);
    PRINT 'Created index: ix_trades_status';
END
GO
