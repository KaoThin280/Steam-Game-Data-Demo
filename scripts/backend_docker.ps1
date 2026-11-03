[CmdletBinding()]
param(
    [ValidateSet('check', 'build', 'up', 'down', 'logs', 'stats', 'verify')]
    [string]$Action = 'check'
)
$ErrorActionPreference = 'Stop'
$backendDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'back_end'
$composeFile = Join-Path $backendDir 'compose.local.yml'
$localEnv = Join-Path $backendDir '.env.docker.local'

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker compose --project-name steam-backend-local --env-file $localEnv -f $composeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $($ComposeArgs -join ' ')" }
}

if (!(Test-Path -LiteralPath $localEnv)) {
    throw 'Copy back_end/.env.docker.example to back_end/.env.docker.local and fill development credentials first.'
}
switch ($Action) {
    'check' { Invoke-Compose -ComposeArgs @('config', '--quiet') }
    'build' { Invoke-Compose -ComposeArgs @('build') }
    'up' { Invoke-Compose -ComposeArgs @('up', '-d', '--build', '--wait', '--wait-timeout', '300') }
    'down' { Invoke-Compose -ComposeArgs @('down') }
    'logs' { Invoke-Compose -ComposeArgs @('logs', '--tail', '100', '-f') }
    'stats' { Invoke-Compose -ComposeArgs @('stats', '--no-stream') }
    'verify' {
        Invoke-Compose -ComposeArgs @('exec', '-T', 'mcp', 'python', '-m', 'app.healthcheck', 'http://127.0.0.1:8001/health')
        Invoke-Compose -ComposeArgs @('exec', '-T', 'api', 'python', '-m', 'app.healthcheck', 'http://127.0.0.1:8000/health')
        $ids = @(& docker compose --project-name steam-backend-local --env-file $localEnv -f $composeFile ps -q)
        if ($LASTEXITCODE -ne 0 -or $ids.Count -ne 2) { throw 'Expected both API and MCP containers.' }
        foreach ($containerId in $ids) {
            & docker inspect --format '{{.Name}} memory={{.HostConfig.Memory}} memorySwap={{.HostConfig.MemorySwap}} nanoCPUs={{.HostConfig.NanoCpus}} oomKilled={{.State.OOMKilled}} restarts={{.RestartCount}}' $containerId
            if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect container limits.' }
        }
        Invoke-Compose -ComposeArgs @('stats', '--no-stream')
        Write-Host 'Dependency health probes passed. Run feature smoke/load tests before deployment.'
    }
}
