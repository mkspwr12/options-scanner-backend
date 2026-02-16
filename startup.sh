#!/bin/bash
set -e

echo "=== Options Scanner Backend Startup ==="

# ------------------------------------------------------------------
# Install Microsoft ODBC Driver 18 for SQL Server (if not present)
# ------------------------------------------------------------------
if ! odbcinst -q -d -n "ODBC Driver 18 for SQL Server" > /dev/null 2>&1; then
    echo "Installing ODBC Driver 18 for SQL Server..."

    # Detect OS — App Service Linux containers are Debian-based
    . /etc/os-release
    DISTRO="${ID}"
    VERSION="${VERSION_ID}"

    # Import Microsoft GPG key
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
        gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg 2>/dev/null

    if [ "$DISTRO" = "debian" ]; then
        echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/${VERSION}/prod ${VERSION_CODENAME} main" \
            > /etc/apt/sources.list.d/mssql-release.list
    elif [ "$DISTRO" = "ubuntu" ]; then
        echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/ubuntu/${VERSION}/prod ${VERSION_CODENAME} main" \
            > /etc/apt/sources.list.d/mssql-release.list
    else
        echo "WARNING: Unknown distro '${DISTRO}', defaulting to Debian 11"
        echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" \
            > /etc/apt/sources.list.d/mssql-release.list
    fi

    apt-get update -qq
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18
    apt-get clean
    rm -rf /var/lib/apt/lists/*

    echo "ODBC Driver 18 installed successfully."
else
    echo "ODBC Driver 18 already installed."
fi

# List available ODBC drivers for verification
echo "Available ODBC drivers:"
odbcinst -q -d || echo "  (none found)"

# ------------------------------------------------------------------
# Start the application
# ------------------------------------------------------------------
echo "Starting Gunicorn with Uvicorn workers..."
python -m gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
