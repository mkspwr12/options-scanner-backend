-- Migration 005: Create strategies and strategy_legs tables
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'strategies')
BEGIN
    CREATE TABLE strategies (
        id               VARCHAR(50)    NOT NULL PRIMARY KEY,
        strategy_type    VARCHAR(30)    NOT NULL,
        name             VARCHAR(100)   NULL,
        ticker           VARCHAR(10)    NOT NULL,
        underlying_price DECIMAL(12,4)  NULL,
        status           VARCHAR(20)    NOT NULL DEFAULT 'active',
        entry_date       DATETIME2      NULL,
        exit_date        DATETIME2      NULL,
        last_updated     DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        tags             VARCHAR(500)   NULL,
        notes            NVARCHAR(MAX)  NULL,

        CONSTRAINT chk_strategy_status CHECK (status IN ('active', 'closed', 'expired'))
    );

    PRINT 'Created table: strategies';
END
ELSE
    PRINT 'Table strategies already exists — skipping';
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'strategy_legs')
BEGIN
    CREATE TABLE strategy_legs (
        id                  VARCHAR(50)    NOT NULL PRIMARY KEY,
        strategy_id         VARCHAR(50)    NOT NULL,
        leg_index           INT            NOT NULL,
        type                VARCHAR(10)    NOT NULL,
        strike              DECIMAL(12,4)  NOT NULL,
        expiration          VARCHAR(10)    NOT NULL,
        action              VARCHAR(10)    NOT NULL,
        quantity            INT            NOT NULL,
        entry_price         DECIMAL(12,4)  NULL,
        current_price       DECIMAL(12,4)  NULL,
        delta               DECIMAL(10,6)  NULL,
        gamma               DECIMAL(10,6)  NULL,
        theta               DECIMAL(10,6)  NULL,
        vega                DECIMAL(10,6)  NULL,
        implied_volatility  DECIMAL(10,6)  NULL,

        CONSTRAINT fk_strategy_legs_strategy FOREIGN KEY (strategy_id)
            REFERENCES strategies(id) ON DELETE CASCADE,
        CONSTRAINT chk_leg_type CHECK (type IN ('CALL', 'PUT')),
        CONSTRAINT chk_leg_action CHECK (action IN ('BUY', 'SELL'))
    );

    PRINT 'Created table: strategy_legs';
END
ELSE
    PRINT 'Table strategy_legs already exists — skipping';
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_strategies_ticker' AND object_id = OBJECT_ID('strategies'))
BEGIN
    CREATE INDEX ix_strategies_ticker ON strategies(ticker);
    PRINT 'Created index: ix_strategies_ticker';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_strategies_status' AND object_id = OBJECT_ID('strategies'))
BEGIN
    CREATE INDEX ix_strategies_status ON strategies(status);
    PRINT 'Created index: ix_strategies_status';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_strategy_legs_strategy_id' AND object_id = OBJECT_ID('strategy_legs'))
BEGIN
    CREATE INDEX ix_strategy_legs_strategy_id ON strategy_legs(strategy_id);
    PRINT 'Created index: ix_strategy_legs_strategy_id';
END
GO
