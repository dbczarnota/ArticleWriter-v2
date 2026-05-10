# scripts/dev-prod-db.ps1
#
# Local dev session against production Postgres via kubectl port-forward.
# No deploy needed. Ctrl+C to stop.
#
# Prerequisites (one-time):
#   - kubectl configured for the production cluster
#   - Kinde dashboard: http://localhost:5173 added as allowed redirect URI
#     (see docs/dev-workflow.md for instructions)
#
# Usage:
#   .\scripts\dev-prod-db.ps1
#   Then in a second terminal: cd frontend && npm run dev

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

# Ensure kubeconfig is set (in case terminal predates profile change)
if (-not $env:KUBECONFIG) {
    $env:KUBECONFIG = "C:\Users\czarn\.kube\headlinesforge.yaml"
}

$Namespace = "headlinesforge"
$LocalPort  = 5433

# --- 1. Load .env (API keys, Kinde config, etc.) — skip DATABASE_URL ---
Write-Host "[1/4] Loading .env (skipping DATABASE_URL — will use prod)..."
$envFile = Join-Path $PSScriptRoot "..\.env"
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
        $key = $Matches[1].Trim()
        $val = $Matches[2].Trim().Trim('"').Trim("'")
        # Skip DATABASE_URL — we'll set it from prod secrets below
        if ($key -ne "DATABASE_URL" -and $key -ne "POSTGRES_PASSWORD") {
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

# --- 2. Fetch prod POSTGRES_PASSWORD from k8s, build local DATABASE_URL ---
Write-Host "[2/4] Fetching POSTGRES_PASSWORD from k8s secret..."
try {
    $encoded = kubectl get secret headlinesforge-secrets -n $Namespace -o "jsonpath={.data.POSTGRES_PASSWORD}" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "kubectl exited ${LASTEXITCODE}: $encoded" }
    $password = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encoded.Trim()))
} catch {
    Write-Host ""
    Write-Host "ERROR: Could not fetch k8s secret." -ForegroundColor Red
    Write-Host "  Check kubectl is configured: kubectl get nodes"
    Write-Host "  Then: kubectl get secret headlinesforge-secrets -n $Namespace"
    Write-Host "  Error: $_"
    exit 1
}

$localUrl = "postgresql+asyncpg://articlewriter:${password}@localhost:${LocalPort}/articlewriter"
$env:DATABASE_URL  = $localUrl
$env:DB_BACKEND    = "postgres"
$env:AUTH_BACKEND  = "kinde"

$maskedUrl = $localUrl -replace ":([^:@]+)@", ":***@"
Write-Host "         DATABASE_URL = $maskedUrl"

# --- 3. Start port-forward in background ---
Write-Host "[3/4] Starting kubectl port-forward (prod postgres -> localhost:$LocalPort)..."
$pf = Start-Process -FilePath "kubectl" `
    -ArgumentList "port-forward", "svc/postgres", "${LocalPort}:5432", "-n", $Namespace `
    -PassThru -NoNewWindow

Write-Host "         Czekam na port $LocalPort..." -NoNewline
$deadline = (Get-Date).AddSeconds(20)
while ($true) {
    if ($pf.HasExited) {
        Write-Host ""
        Write-Host "ERROR: port-forward exited. Check kubectl access and namespace." -ForegroundColor Red
        exit 1
    }
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $LocalPort)
        $tcp.Close()
        Write-Host " gotowy."
        break
    } catch {}
    if ((Get-Date) -gt $deadline) {
        Write-Host ""
        Write-Host "ERROR: port-forward nie odpowiada po 20s." -ForegroundColor Red
        $pf.Kill()
        exit 1
    }
    Start-Sleep -Milliseconds 500
    Write-Host "." -NoNewline
}

Write-Host "         Port-forward running (PID $($pf.Id))"

# --- 4. Apply pending migrations ---
Write-Host "[4/5] Applying Alembic migrations (alembic upgrade head)..."
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Alembic migration failed. Fix the migration before starting the backend." -ForegroundColor Red
    $pf.Kill()
    exit 1
}
Write-Host "         Migrations OK."

# --- 5. Run backend ---
Write-Host "[5/5] Starting backend (uvicorn)..."
Write-Host ""
Write-Host "  Backend:  http://localhost:8000/health"
Write-Host "  Frontend: open a new terminal -> cd frontend && npm run dev"
Write-Host "  App:      http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop."
Write-Host ""

try {
    uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
} finally {
    if (-not $pf.HasExited) {
        $pf.Kill()
        Write-Host "Port-forward stopped."
    }
}
