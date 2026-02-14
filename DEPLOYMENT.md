# Backend Deployment Guide

## GitHub Actions Setup

This repository uses GitHub Actions for automated deployment to Azure App Service.

### Required GitHub Secrets

Configure the following secrets in your GitHub repository (Settings → Secrets and variables → Actions):

#### 1. AZURE_CREDENTIALS

Service principal credentials for Azure authentication. Create using:

```bash
az ad sp create-for-rbac \
  --name "options-scanner-backend-deploy" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/options-scanner-rg \
  --sdk-auth
```

Copy the entire JSON output to this secret.

#### 2. SQL_CONNECTION_STRING

Azure SQL Database connection string:

```
Driver={ODBC Driver 18 for SQL Server};Server=tcp:options-scanner-sql-2exk6s.database.windows.net,1433;Database=portfolio_db;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

**Note:** Do NOT include UID/PWD in the connection string - Managed Identity authentication is used.

#### 3. AZURE_CLIENT_ID (Optional)

Client ID of the user-assigned managed identity. Only required if using a user-assigned managed identity:

```
{managed-identity-client-id}
```

Get this value using:

```bash
az identity show \
  --resource-group options-scanner-rg \
  --name options-scanner-identity-2exk6s \
  --query clientId -o tsv
```

### Deployment Process

1. **Automatic Deployment**: Push to `main` branch triggers automatic deployment
2. **Manual Deployment**: Use "Run workflow" button in Actions tab

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export SQL_CONNECTION_STRING="Driver={ODBC Driver 18 for SQL Server};Server=tcp:localhost,1433;Database=portfolio_db;UID=sa;PWD=yourpassword;Encrypt=yes;TrustServerCertificate=yes"
   ```

3. Run locally:
   ```bash
   uvicorn app.main:app --reload
   ```

### Azure App Service Configuration

The backend is configured to use:
- **Python Version**: 3.11
- **Startup Command**: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Managed Identity**: System-assigned or user-assigned for SQL authentication
- **Health Check**: `/health` endpoint

### Troubleshooting

**Connection String Issues:**
- Ensure the connection string does NOT include `UID=` or `PWD=` parameters
- Managed Identity requires SQL Server to have Azure AD authentication enabled
- Verify the App Service's managed identity has `db_datareader` and `db_datawriter` roles

**Deployment Failures:**
- Check GitHub Actions logs for detailed error messages
- Verify Azure credentials have not expired
- Ensure App Service is configured for Python 3.11
