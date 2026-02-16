-- Migration 004: Create providers table
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'providers')
BEGIN
    CREATE TABLE providers (
        id                       VARCHAR(50)    NOT NULL PRIMARY KEY,
        name                     VARCHAR(100)   NOT NULL,
        type                     VARCHAR(20)    NOT NULL,
        api_key_encrypted        VARBINARY(MAX) NULL,
        api_secret_encrypted     VARBINARY(MAX) NULL,
        base_url                 VARCHAR(255)   NOT NULL,
        enabled                  BIT            NOT NULL DEFAULT 1,
        priority                 INT            NOT NULL,
        rate_limit_max_per_hour  INT            DEFAULT 2000,
        rate_limit_max_per_day   INT            DEFAULT 20000,
        rate_limit_cost_per_call DECIMAL(10,4)  DEFAULT 0,
        created_at               DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        updated_at               DATETIME2      NOT NULL DEFAULT GETUTCDATE(),

        CONSTRAINT uq_providers_name UNIQUE (name),
        CONSTRAINT chk_providers_type CHECK (type IN ('YAHOO_FINANCE', 'ALPACA', 'TRADIER', 'CUSTOM', 'MOCK'))
    );

    PRINT 'Created table: providers';
END
ELSE
    PRINT 'Table providers already exists — skipping';
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_providers_priority' AND object_id = OBJECT_ID('providers'))
BEGIN
    CREATE INDEX ix_providers_priority ON providers(priority);
    PRINT 'Created index: ix_providers_priority';
END
GO

-- Seed default Yahoo Finance provider
IF NOT EXISTS (SELECT 1 FROM providers WHERE id = 'yahoo-default')
BEGIN
    INSERT INTO providers (id, name, type, base_url, enabled, priority)
    VALUES ('yahoo-default', 'Yahoo Finance', 'YAHOO_FINANCE',
            'https://query1.finance.yahoo.com', 1, 1);
    PRINT 'Seeded default Yahoo Finance provider';
END
GO
