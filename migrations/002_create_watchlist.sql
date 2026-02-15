-- Migration 002: Create watchlist_items table
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'watchlist_items')
BEGIN
    CREATE TABLE watchlist_items (
        id       INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
        symbol   VARCHAR(10)   NOT NULL,
        added_at DATETIME2     NOT NULL DEFAULT GETUTCDATE(),

        CONSTRAINT uq_watchlist_symbol UNIQUE (symbol)
    );

    PRINT 'Created table: watchlist_items';

    -- Seed default symbols
    INSERT INTO watchlist_items (symbol) VALUES ('META'), ('SPY'), ('AAPL'), ('NVDA');
    PRINT 'Seeded default watchlist symbols: META, SPY, AAPL, NVDA';
END
ELSE
    PRINT 'Table watchlist_items already exists — skipping';
GO
