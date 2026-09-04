[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$McpBaseUrl = "http://127.0.0.1:8001",
    [string]$Email,
    [string]$Password,
    [string]$Task = "How many games and reviews are in the database? Use the available tools and explain the result briefly.",
    [switch]$NoStartServer,
    [switch]$SkipDependencyInstall,
    [switch]$SkipCancelTest,
    [switch]$ConversationSuite,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "back_end"
$PythonPath = Join-Path $BackendDir ".venv\Scripts\python.exe"
$StdoutLog = Join-Path $BackendDir "test_logs\agent-local.stdout.log"
$StderrLog = Join-Path $BackendDir "test_logs\agent-local.stderr.log"
$McpStdoutLog = Join-Path $BackendDir "test_logs\mcp-local.stdout.log"
$McpStderrLog = Join-Path $BackendDir "test_logs\mcp-local.stderr.log"
$script:ServerProcess = $null
$script:McpProcess = $null
$script:OriginalDebug = $env:DEBUG
$script:OriginalSecretKey = $env:SECRET_KEY
$script:OriginalMcpSecret = $env:MCP_SHARED_SECRET
$script:OriginalMcpUrl = $env:MCP_SERVER_URL
$script:OriginalPythonUtf8 = $env:PYTHONUTF8
$script:OriginalPythonIoEncoding = $env:PYTHONIOENCODING

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Convert-SecurePassword([Security.SecureString]$SecurePassword) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-DotEnvValue([string]$Name) {
    $envFile = Join-Path $BackendDir ".env"
    if (-not (Test-Path -LiteralPath $envFile)) { return $null }
    $line = Get-Content -LiteralPath $envFile | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$"
    } | Select-Object -Last 1
    if (-not $line) { return $null }
    $value = ($line -split '=', 2)[1].Trim()
    return $value.Trim('"').Trim("'")
}

function Invoke-AgentApi {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body,
        [string]$AccessToken
    )

    $parameters = @{
        Method = $Method
        Uri = "$BaseUrl$Path"
        ContentType = "application/json; charset=utf-8"
        TimeoutSec = 30
    }
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 10 -Compress
        # Windows PowerShell 5.1 may otherwise calculate Content-Length from
        # characters while sending a different byte encoding for Vietnamese.
        $parameters.Body = [Text.Encoding]::UTF8.GetBytes($jsonBody)
    }
    if ($AccessToken) {
        $parameters.Headers = @{ Authorization = "Bearer $AccessToken" }
    }
    return Invoke-RestMethod @parameters
}

function Test-Health {
    try {
        $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -TimeoutSec 3
        return $health.status -in @("healthy", "degraded")
    }
    catch {
        return $false
    }
}

function Wait-ForServer {
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health) { return }
        if ($script:ServerProcess -and $script:ServerProcess.HasExited) {
            throw "Backend exited during startup. Read $StderrLog"
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Backend did not become ready in 30 seconds. Read $StderrLog"
}

function Wait-ForMcpServer {
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Method Get -Uri "$McpBaseUrl/health" -TimeoutSec 3
            if ($health.status -eq "healthy") { return }
        }
        catch {}
        if ($script:McpProcess -and $script:McpProcess.HasExited) {
            throw "MCP server exited during startup. Read $McpStderrLog"
        }
        Start-Sleep -Milliseconds 500
    }
    throw "MCP server did not become ready in 30 seconds. Read $McpStderrLog"
}

function Initialize-PythonDependencies {
    & $PythonPath -c "import uvicorn, fastapi, sqlalchemy, openai" 2>$null
    if ($LASTEXITCODE -eq 0) { return }

    if ($SkipDependencyInstall) {
        throw "Required Python packages are missing and -SkipDependencyInstall was specified."
    }

    Write-Step "Installing missing backend dependencies"
    & $PythonPath -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Run '$PythonPath -m pip install -r back_end\requirements.txt' manually."
    }

    & $PythonPath -c "import uvicorn, fastapi, sqlalchemy, openai"
    if ($LASTEXITCODE -ne 0) {
        throw "Dependencies were installed but the backend modules still cannot be imported."
    }
}

function Set-LocalSecurityEnvironment {
    # Environment variables override .env only for this PowerShell process and
    # the Uvicorn child. Nothing is written to disk or propagated to the VPS.
    $randomBytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($randomBytes)
    }
    finally {
        $rng.Dispose()
    }
    $env:DEBUG = "true"
    $env:SECRET_KEY = [Convert]::ToBase64String($randomBytes)
    $env:MCP_SHARED_SECRET = [Convert]::ToBase64String($randomBytes)
    $env:MCP_SERVER_URL = "$McpBaseUrl/mcp"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
}

function Assert-RequiredLocalConfiguration {
    $envFile = Join-Path $BackendDir ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        throw "Missing back_end\.env. Copy .env.example and configure the local services first."
    }

    $readonlyConfigured = -not [string]::IsNullOrWhiteSpace($env:DATABASE_URL_READONLY)
    if (-not $readonlyConfigured) {
        $line = Get-Content -LiteralPath $envFile | Where-Object {
            $_ -match '^\s*DATABASE_URL_READONLY\s*=\s*(.+?)\s*$'
        } | Select-Object -Last 1
        if ($line -and $line -match '^\s*DATABASE_URL_READONLY\s*=\s*(.+?)\s*$') {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            $readonlyConfigured = -not [string]::IsNullOrWhiteSpace($value) `
                -and $value -notmatch 'PASSWORD|HOST|CHANGE_ME'
        }
    }
    if (-not $readonlyConfigured) {
        throw "DATABASE_URL_READONLY is empty or still a placeholder in back_end\.env. Configure the steam_readonly Supabase connection first."
    }
}

function Wait-ForRun {
    param(
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$AccessToken
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = $null
    while ((Get-Date) -lt $deadline) {
        $run = Invoke-AgentApi -Method Get -Path "/api/v1/agent-rpc/runs/$RunId" -AccessToken $AccessToken
        if ($run.status -ne $lastStatus) {
            Write-Host "Run status: $($run.status), step $($run.current_step)/$($run.max_steps)"
            $lastStatus = $run.status
        }
        if ($run.status -in @("completed", "failed", "cancelled")) {
            return $run
        }
        Start-Sleep -Milliseconds 750
    }
    throw "Run $RunId did not finish within $TimeoutSeconds seconds."
}

function Invoke-ConversationTurn {
    param(
        [string]$SessionId,
        [string]$Question,
        [string]$AccessToken,
        [bool]$ExpectTool,
        [bool]$ExpectChart = $false
    )
    Write-Host "`nQ: $Question" -ForegroundColor Yellow
    $submitted = Invoke-AgentApi -Method Post `
        -Path "/api/v1/agent-rpc/sessions/$SessionId/tasks" `
        -Body @{ message = $Question } -AccessToken $AccessToken
    $run = Wait-ForRun -RunId $submitted.run_id -AccessToken $AccessToken
    if ($run.status -ne "completed") {
        throw "Conversation run $($submitted.run_id) ended as $($run.status)."
    }
    $events = Invoke-AgentApi -Method Get `
        -Path "/api/v1/agent-rpc/runs/$($submitted.run_id)/events" `
        -AccessToken $AccessToken
    if ($ExpectTool -and -not ($events.type -contains "tool.finished")) {
        throw "Question required data but no completed tool call was recorded."
    }
    if ($ExpectChart) {
        $chartEvent = $events | Where-Object {
            $_.type -eq "tool.finished" -and $null -ne $_.payload.result.content.chart
        } | Select-Object -First 1
        if (-not $chartEvent) {
            throw "Chart question completed without a renderable MCP chart payload."
        }
        Write-Host "Chart payload: $($chartEvent.payload.result.content.chart.type), $($chartEvent.payload.result.content.chart.x.Count) points"
        if ($chartEvent.payload.result.content.truncated) {
            throw "The specialized monthly chart payload was unexpectedly truncated."
        }
        if ($chartEvent.payload.result.content.chart.x.Count -le 200) {
            throw "Expected the complete monthly timeline (>200 points), but received $($chartEvent.payload.result.content.chart.x.Count)."
        }
    }
    Write-Host "A: $($run.output)" -ForegroundColor Green
    return $run
}

try {
    if (-not $Email) {
        $Email = if ($env:LOCAL_TEST_EMAIL) {
            $env:LOCAL_TEST_EMAIL
        } else {
            Get-DotEnvValue "LOCAL_TEST_EMAIL"
        }
    }
    if (-not $Password) {
        $Password = if ($env:LOCAL_TEST_PASSWORD) {
            $env:LOCAL_TEST_PASSWORD
        } else {
            Get-DotEnvValue "LOCAL_TEST_PASSWORD"
        }
    }
    if (-not $Email) {
        throw "Provide -Email or set LOCAL_TEST_EMAIL in back_end\.env."
    }

    if (-not (Test-Health)) {
        if ($NoStartServer) {
            throw "Backend is not reachable at $BaseUrl and -NoStartServer was specified."
        }
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            throw "Python venv not found at $PythonPath. Create it and install back_end/requirements.txt first."
        }
        Initialize-PythonDependencies
        Set-LocalSecurityEnvironment
        Assert-RequiredLocalConfiguration
        New-Item -ItemType Directory -Force -Path (Split-Path $StdoutLog) | Out-Null
        Write-Step "Starting independent local MCP server"
        $script:McpProcess = Start-Process `
            -FilePath $PythonPath `
            -ArgumentList "-m", "uvicorn", "app.mcp_server:app", "--host", "127.0.0.1", "--port", "8001" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $McpStdoutLog `
            -RedirectStandardError $McpStderrLog `
            -WindowStyle Hidden `
            -PassThru
        Wait-ForMcpServer
        Write-Step "Starting local backend"
        $script:ServerProcess = Start-Process `
            -FilePath $PythonPath `
            -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $StdoutLog `
            -RedirectStandardError $StderrLog `
            -WindowStyle Hidden `
            -PassThru
        Wait-ForServer
    }

    Write-Step "Checking backend health"
    $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -TimeoutSec 5
    Write-Host "API status: $($health.status); database: $($health.database); redis: $($health.redis)"
    if ($health.status -ne "healthy") {
        throw "Backend health is degraded. Fix database/Redis connectivity before agent testing."
    }

    Write-Step "Logging in"
    if (-not $Password) {
        $securePassword = Read-Host "Password for $Email" -AsSecureString
        $Password = Convert-SecurePassword $securePassword
    }
    $login = Invoke-AgentApi -Method Post -Path "/api/v1/auth/login" -Body @{
        email = $Email
        password = $Password
    }
    $accessToken = $login.access_token
    if (-not $accessToken) { throw "Login response did not contain an access token." }
    $Password = $null

    if ($ConversationSuite) {
        Write-Step "Running two-session multilingual conversation suite"
        $suites = @(
            @{
                Title = "Vietnamese conversation"
                Questions = @(
                    ('"B\u1ea1n l\u00e0 ai?"' | ConvertFrom-Json),
                    ('"T\u1ed5ng s\u1ed1 l\u01b0\u1ee3ng game m\u00e0 h\u1ec7 th\u1ed1ng hi\u1ec7n c\u00f3 l\u00e0 bao nhi\u00eau?"' | ConvertFrom-Json),
                    ('"Bi\u1ec3u \u0111\u1ed3 s\u1ed1 l\u01b0\u1ee3ng game m\u1edbi theo c\u00e1c th\u00e1ng qua th\u1eddi gian."' | ConvertFrom-Json)
                )
            },
            @{
                Title = "English conversation"
                Questions = @(
                    "Who are you?",
                    "What is the total number of games currently in the system?",
                    "Show a chart of new game counts by month over time."
                )
            }
        )
        $sessionIds = @()
        foreach ($suite in $suites) {
            $created = Invoke-AgentApi -Method Post -Path "/api/v1/agent-rpc/sessions" `
                -Body @{ title = $suite.Title } -AccessToken $accessToken
            $sessionIds += $created.session_id
            Write-Host "`nSession '$($suite.Title)': $($created.session_id)" -ForegroundColor Cyan
            for ($index = 0; $index -lt $suite.Questions.Count; $index++) {
                Invoke-ConversationTurn -SessionId $created.session_id `
                    -Question $suite.Questions[$index] -AccessToken $accessToken `
                    -ExpectTool ($index -gt 0) -ExpectChart ($index -eq 2) | Out-Null
            }
            $detail = Invoke-AgentApi -Method Get `
                -Path "/api/v1/agent-rpc/sessions/$($created.session_id)" `
                -AccessToken $accessToken
            if ($detail.runs.Count -ne 3) {
                throw "Expected 3 persisted turns in '$($suite.Title)', got $($detail.runs.Count)."
            }
        }
        if ($sessionIds[0] -eq $sessionIds[1]) {
            throw "The two conversation suites unexpectedly share one session ID."
        }
        Write-Host "`nPASS: two isolated sessions retained all three turns." -ForegroundColor Green
        return
    }

    Write-Step "Creating a persistent agent session"
    $session = Invoke-AgentApi -Method Post -Path "/api/v1/agent-rpc/sessions" `
        -Body @{ title = "Local smoke test $(Get-Date -Format s)" } -AccessToken $accessToken
    Write-Host "Session: $($session.session_id)"

    Write-Step "Submitting an end-to-end MCP task"
    $submitted = Invoke-AgentApi -Method Post `
        -Path "/api/v1/agent-rpc/sessions/$($session.session_id)/tasks" `
        -Body @{ message = $Task } -AccessToken $accessToken
    Write-Host "Run: $($submitted.run_id)"

    $run = Wait-ForRun -RunId $submitted.run_id -AccessToken $accessToken
    $events = Invoke-AgentApi -Method Get `
        -Path "/api/v1/agent-rpc/runs/$($submitted.run_id)/events" `
        -AccessToken $accessToken

    Write-Host "Events: $($events.Count)"
    $events | ForEach-Object {
        Write-Host ("  #{0} {1}" -f $_.sequence, $_.type)
    }
    if ($run.status -ne "completed") {
        $errorText = if ($run.error) { "$($run.error.code): $($run.error.message)" } else { "no error details" }
        throw "Main agent run ended as '$($run.status)': $errorText"
    }
    if (-not ($events.type -contains "tool.started") -or -not ($events.type -contains "tool.finished")) {
        throw "Run completed but no MCP tool lifecycle was recorded. Try a more explicit data task."
    }
    Write-Host "Answer: $($run.output)" -ForegroundColor Green

    if (-not $SkipCancelTest) {
        Write-Step "Testing durable cancellation"
        $cancelRun = Invoke-AgentApi -Method Post `
            -Path "/api/v1/agent-rpc/sessions/$($session.session_id)/tasks" `
            -Body @{ message = "Analyze the game and review data in several steps." } `
            -AccessToken $accessToken
        $cancelResponse = Invoke-AgentApi -Method Post `
            -Path "/api/v1/agent-rpc/runs/$($cancelRun.run_id)/cancel" `
            -AccessToken $accessToken
        Write-Host "Cancel request: $($cancelResponse.status)"
        $cancelled = Wait-ForRun -RunId $cancelRun.run_id -AccessToken $accessToken
        if ($cancelled.status -ne "cancelled") {
            throw "Expected cancelled status, received '$($cancelled.status)'."
        }
        $cancelEvents = Invoke-AgentApi -Method Get `
            -Path "/api/v1/agent-rpc/runs/$($cancelRun.run_id)/events" `
            -AccessToken $accessToken
        if (-not ($cancelEvents.type -contains "cancellation.requested")) {
            throw "Cancellation state persisted but its trace event is missing."
        }
    }

    Write-Host "`nPASS: local backend agent smoke test completed." -ForegroundColor Green
}
catch {
    Write-Host "`nFAIL: $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path -LiteralPath $StderrLog) {
        Write-Host "Backend error log: $StderrLog" -ForegroundColor Yellow
    }
    exit 1
}
finally {
    $Password = $null
    if ($script:ServerProcess -and -not $script:ServerProcess.HasExited) {
        Write-Step "Stopping backend process started by this script"
        Stop-Process -Id $script:ServerProcess.Id
        $script:ServerProcess.WaitForExit()
    }
    if ($script:McpProcess -and -not $script:McpProcess.HasExited) {
        Write-Step "Stopping MCP process started by this script"
        Stop-Process -Id $script:McpProcess.Id
        $script:McpProcess.WaitForExit()
    }
    $env:DEBUG = $script:OriginalDebug
    $env:SECRET_KEY = $script:OriginalSecretKey
    $env:MCP_SHARED_SECRET = $script:OriginalMcpSecret
    $env:MCP_SERVER_URL = $script:OriginalMcpUrl
    $env:PYTHONUTF8 = $script:OriginalPythonUtf8
    $env:PYTHONIOENCODING = $script:OriginalPythonIoEncoding
}
