-- Migration 006: Create provider_metrics table
-- Idempotent: safe to re-run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'provider_metrics')
BEGIN
    CREATE TABLE provider_metrics (
        id              VARCHAR(50)    NOT NULL PRIMARY KEY,
        provider_id     VARCHAR(50)    NOT NULL,
        endpoint        VARCHAR(100)   NOT NULL,
        latency_ms      INT            NOT NULL,
        success         BIT            NOT NULL,
        error_message   NVARCHAR(500)  NULL,
        recorded_at     DATETIME2      NOT NULL DEFAULT GETUTCDATE(),

        CONSTRAINT fk_metrics_provider FOREIGN KEY (provider_id)
            REFERENCES providers(id) ON DELETE CASCADE
    );

    PRINT 'Created table: provider_metrics';
END
ELSE
    PRINT 'Table provider_metrics already exists — skipping';
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_metrics_provider_recorded' AND object_id = OBJECT_ID('provider_metrics'))
BEGIN
    CREATE INDEX ix_metrics_provider_recorded ON provider_metrics(provider_id, recorded_at DESC);
    PRINT 'Created index: ix_metrics_provider_recorded';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_metrics_recorded_at' AND object_id = OBJECT_ID('provider_metrics'))
BEGIN
    CREATE INDEX ix_metrics_recorded_at ON provider_metrics(recorded_at DESC);
    PRINT 'Created index: ix_metrics_recorded_at';
END
GO
