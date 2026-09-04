[CmdletBinding()]
param(
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000,
    [int]$McpPort = 8001,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "back_end"
$FrontendDir = Join-Path $ProjectRoot "front_end"
$PythonPath = Join-Path $BackendDir ".venv\Scripts\python.exe"
$LogDir = Join-Path $BackendDir "test_logs"
$Processes = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-PortAvailable([int]$Port, [string]$Service) {
    $occupied = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($occupied) {
        throw "$Service cannot start: port $Port is already in use (PID $($occupied[0].OwningProcess))."
    }
}

function Wait-Http([string]$Url, [System.Diagnostics.Process]$Process, [string]$Name) {
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { throw "$Name exited during startup. Check its log in $LogDir." }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready at $Url within 45 seconds."
}

function Start-LoggedProcess {
    param([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory)
    $stdout = Join-Path $LogDir "$Name.stdout.log"
    $stderr = Join-Path $LogDir "$Name.stderr.log"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $Processes.Add($process)
    return $process
}

$OriginalEnvironment = @{
    DEBUG = $env:DEBUG
    SECRET_KEY = $env:SECRET_KEY
    MCP_SHARED_SECRET = $env:MCP_SHARED_SECRET
    MCP_SERVER_URL = $env:MCP_SERVER_URL
    PYTHONUTF8 = $env:PYTHONUTF8
    PYTHONIOENCODING = $env:PYTHONIOENCODING
    NEXT_PUBLIC_API_URL = $env:NEXT_PUBLIC_API_URL
}

try {
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        throw "Missing $PythonPath. Create the backend virtual environment first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
        throw "Missing front_end\node_modules. Run 'npm install' inside front_end first."
    }

    Assert-PortAvailable $McpPort "MCP server"
    Assert-PortAvailable $BackendPort "Backend"
    Assert-PortAvailable $FrontendPort "Frontend"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $secret = [Convert]::ToBase64String($bytes)
    $env:DEBUG = "true"
    $env:SECRET_KEY = $secret
    $env:MCP_SHARED_SECRET = $secret
    $env:MCP_SERVER_URL = "http://127.0.0.1:$McpPort/mcp"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$BackendPort/api/v1"

    $reloadArgs = if ($NoReload) { @() } else { @("--reload") }

    Write-Step "Starting independent MCP server on port $McpPort"
    $mcp = Start-LoggedProcess "local-mcp" $PythonPath `
        (@("-m", "uvicorn", "app.mcp_server:app", "--host", "127.0.0.1", "--port", "$McpPort") + $reloadArgs) $BackendDir
    Wait-Http "http://127.0.0.1:$McpPort/health" $mcp "MCP server"

    Write-Step "Starting backend on port $BackendPort"
    $backend = Start-LoggedProcess "local-backend" $PythonPath `
        (@("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$BackendPort") + $reloadArgs) $BackendDir
    Wait-Http "http://127.0.0.1:$BackendPort/health" $backend "Backend"

    Write-Step "Starting Next.js frontend on port $FrontendPort"
    $npmPath = (Get-Command npm.cmd -ErrorAction Stop).Source
    $frontend = Start-LoggedProcess "local-frontend" $npmPath `
        @("run", "dev", "--", "--hostname", "0.0.0.0", "--port", "$FrontendPort") $FrontendDir
    Wait-Http "http://127.0.0.1:$FrontendPort/login" $frontend "Frontend"

    Write-Host "`nLocal stack is ready:" -ForegroundColor Green
    Write-Host "  Frontend : http://localhost:$FrontendPort"
    Write-Host "  Login    : http://localhost:$FrontendPort/login"
    Write-Host "  Dashboard: http://localhost:$FrontendPort/dashboard"
    Write-Host "  AI Chat  : http://localhost:$FrontendPort/chat"
    Write-Host "  API docs : http://localhost:$BackendPort/docs"
    Write-Host "  MCP      : http://localhost:$McpPort/health (internal service)"
    Write-Host "`nLogs: $LogDir"
    Write-Host "Press Ctrl+C to stop all three services." -ForegroundColor Yellow

    while ($true) {
        foreach ($process in $Processes) {
            if ($process.HasExited) { throw "A local service exited unexpectedly (PID $($process.Id)). Check $LogDir." }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Step "Stopping local stack"
    foreach ($process in $Processes) {
        if ($process -and -not $process.HasExited) {
            # Stop the complete tree (Uvicorn reloaders and npm spawn child
            # processes) so ports are not left occupied after Ctrl+C.
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
    foreach ($key in $OriginalEnvironment.Keys) {
        Set-Item -Path "Env:$key" -Value $OriginalEnvironment[$key] -ErrorAction SilentlyContinue
        if ($null -eq $OriginalEnvironment[$key]) { Remove-Item -Path "Env:$key" -ErrorAction SilentlyContinue }
    }
}
