param(
    [ValidateSet("setup", "start", "stop", "restart", "status", "logs")]
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$ConfigFile = Join-Path $Root "config\quant.env"
$ConfigExample = Join-Path $Root "config\quant.env.example"
$PidDir = Join-Path $Root ".pids"
$LogDir = Join-Path $Root ".logs"
$BackendPid = Join-Path $PidDir "backend-windows.pid"
$FrontendPid = Join-Path $PidDir "frontend-windows.pid"
$BackendLog = Join-Path $LogDir "backend-windows.log"
$FrontendLog = Join-Path $LogDir "frontend-windows.log"
$WslPython = "/root/quantlab/quant/.venv/bin/python"
$WslRoot = "/mnt/c/Users/14116/Documents/quantlab-windows/quant-public"

function Write-Info([string]$Message) {
    Write-Host "[QuantLab] $Message" -ForegroundColor Cyan
}

function Read-Config {
    $values = @{}
    if (Test-Path -LiteralPath $ConfigFile) {
        foreach ($line in Get-Content -LiteralPath $ConfigFile -Encoding UTF8) {
            $trimmed = $line.Trim()
            if (!$trimmed -or $trimmed.StartsWith("#") -or !$trimmed.Contains("=")) {
                continue
            }
            $key, $value = $trimmed.Split("=", 2)
            $values[$key.Trim()] = $value.Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

function Test-Url([string]$Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-NativeBackend {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $VenvPython -c "import uvicorn, fastapi, pandas" 2>$null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Wait-Url([string]$Url, [string]$Name, [string]$LogFile) {
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Url $Url) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    if (Test-Path -LiteralPath $LogFile) {
        Get-Content -LiteralPath $LogFile -Tail 30
    }
    throw "$Name failed to start. See $LogFile"
}

function Stop-ProcessTree([int]$ProcessId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-ProcessTree ([int]$_.ProcessId) }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-FromPidFile([string]$PidFile, [string]$Name) {
    if (!(Test-Path -LiteralPath $PidFile)) {
        Write-Info "$Name is not running."
        return
    }
    $processId = [int](Get-Content -LiteralPath $PidFile -Raw)
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        Stop-ProcessTree $processId
        Write-Info "$Name stopped."
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Invoke-Setup {
    New-Item -ItemType Directory -Force -Path $PidDir, $LogDir | Out-Null
    if (!(Test-Path -LiteralPath $ConfigFile)) {
        Copy-Item -LiteralPath $ConfigExample -Destination $ConfigFile
        Write-Info "Created config\quant.env. Add your own tokens when needed."
    }
    if (!(Test-Path -LiteralPath $VenvPython)) {
        Write-Info "Creating Python virtual environment..."
        & py -3.11 -m venv (Join-Path $Root ".venv")
    }
    Write-Info "Checking backend dependencies..."
    if (!(Test-NativeBackend)) {
        Write-Info "Native packages are incomplete; trying PyPI..."
        & $VenvPython -m pip install -e $Root -i https://pypi.org/simple
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Native install is unavailable. The launcher will use the existing WSL Python environment."
        & wsl.exe -d Ubuntu-24.04 -e $WslPython -c "import uvicorn, fastapi, pandas"
        if ($LASTEXITCODE -ne 0) { throw "Neither Windows nor WSL backend dependencies are available." }
    }

    Write-Info "Installing frontend dependencies..."
    Push-Location (Join-Path $Root "web")
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    } finally {
        Pop-Location
    }
}

function Start-Services {
    if (!(Test-Path -LiteralPath (Join-Path $Root "web\node_modules"))) {
        Invoke-Setup
    }
    New-Item -ItemType Directory -Force -Path $PidDir, $LogDir | Out-Null

    $config = Read-Config
    $backendHost = if ($config.QUANT_BACKEND_HOST) { $config.QUANT_BACKEND_HOST } else { "127.0.0.1" }
    $backendPort = if ($config.QUANT_BACKEND_PORT) { $config.QUANT_BACKEND_PORT } else { "8001" }
    $frontendHost = if ($config.QUANT_FRONTEND_HOST) { $config.QUANT_FRONTEND_HOST } else { "127.0.0.1" }
    $frontendPort = if ($config.QUANT_FRONTEND_PORT) { $config.QUANT_FRONTEND_PORT } else { "5174" }
    $backendUrl = "http://127.0.0.1:$backendPort/api/health"
    $frontendUrl = "http://127.0.0.1:$frontendPort"

    if (!(Test-Url $backendUrl)) {
        Write-Info "Starting backend..."
        if (Test-NativeBackend) {
            $backend = Start-Process -FilePath $VenvPython `
                -ArgumentList @("-m", "uvicorn", "server.main:app", "--host", $backendHost, "--port", $backendPort) `
                -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.error"
        } else {
            $backend = Start-Process -FilePath "wsl.exe" `
                -ArgumentList @("-d", "Ubuntu-24.04", "--cd", $WslRoot, "-e", $WslPython, "-m", "uvicorn", "server.main:app", "--host", $backendHost, "--port", $backendPort) `
                -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.error"
        }
        Set-Content -LiteralPath $BackendPid -Value $backend.Id
        Wait-Url $backendUrl "Backend" $BackendLog
    }

    if (!(Test-Url $frontendUrl)) {
        Write-Info "Starting frontend..."
        $frontend = Start-Process -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev", "--", "--host", $frontendHost, "--port", $frontendPort) `
            -WorkingDirectory (Join-Path $Root "web") -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $FrontendLog -RedirectStandardError "$FrontendLog.error"
        Set-Content -LiteralPath $FrontendPid -Value $frontend.Id
        Wait-Url $frontendUrl "Frontend" $FrontendLog
    }

    Write-Host ""
    Write-Host "QuantLab is ready:" -ForegroundColor Green
    Write-Host "  Frontend: $frontendUrl"
    Write-Host "  API docs: http://127.0.0.1:$backendPort/docs"
}

function Show-Status {
    $config = Read-Config
    $backendPort = if ($config.QUANT_BACKEND_PORT) { $config.QUANT_BACKEND_PORT } else { "8001" }
    $frontendPort = if ($config.QUANT_FRONTEND_PORT) { $config.QUANT_FRONTEND_PORT } else { "5174" }
    Write-Host ("Backend: " + $(if (Test-Url "http://127.0.0.1:$backendPort/api/health") { "ready" } else { "stopped" }))
    Write-Host ("Frontend: " + $(if (Test-Url "http://127.0.0.1:$frontendPort") { "ready" } else { "stopped" }))
}

Set-Location $Root
switch ($Command) {
    "setup" { Invoke-Setup }
    "start" { Start-Services }
    "stop" {
        Stop-FromPidFile $FrontendPid "Frontend"
        Stop-FromPidFile $BackendPid "Backend"
    }
    "restart" {
        Stop-FromPidFile $FrontendPid "Frontend"
        Stop-FromPidFile $BackendPid "Backend"
        Start-Services
    }
    "status" { Show-Status }
    "logs" {
        Get-Content -LiteralPath $BackendLog, $FrontendLog -Tail 100 -Wait
    }
}
