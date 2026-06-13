param(
    [ValidateSet("setup", "start", "stop", "restart", "status", "logs")]
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$ConfigFile = Join-Path $Root "config\quant.env"
$ConfigExample = Join-Path $Root "config\quant.env.example"
$PidDir = Join-Path $Root ".pids"
$LogDir = Join-Path $Root ".logs"
$BackendPid = Join-Path $PidDir "backend-windows.pid"
$FrontendPid = Join-Path $PidDir "frontend-windows.pid"
$BackendLog = Join-Path $LogDir "backend-windows.log"
$FrontendLog = Join-Path $LogDir "frontend-windows.log"

function Write-Info([string]$Message) {
    Write-Host "[QuantLab] $Message" -ForegroundColor Cyan
}

function Invoke-Native([string]$FilePath, [string[]]$Arguments) {
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

function Get-PythonLauncher {
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        foreach ($version in @("3.12", "3.11", "3.10")) {
            $oldPreference = $ErrorActionPreference
            $ErrorActionPreference = "SilentlyContinue"
            try {
                & py.exe "-$version" -c "import sys; raise SystemExit(0 if sys.maxsize > 2**32 else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    return @{ File = "py.exe"; Args = @("-$version") }
                }
            } finally {
                $ErrorActionPreference = $oldPreference
            }
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $version = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($version -in @("3.10", "3.11", "3.12")) {
            return @{ File = $python.Source; Args = @() }
        }
    }
    throw "Python 3.10, 3.11, or 3.12 (64-bit) was not found. Install Python from https://www.python.org/downloads/windows/ and enable 'Add Python to PATH'."
}

function Assert-Node {
    if (!(Get-Command node.exe -ErrorAction SilentlyContinue) -or
        !(Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "Node.js was not found. Install the current Node.js LTS from https://nodejs.org/."
    }
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

function Test-BackendEnvironment {
    if (!(Test-Path -LiteralPath $VenvPython)) { return $false }
    $code = Invoke-Native $VenvPython @(
        "-c",
        "import fastapi, pandas, pyarrow, uvicorn; import server.main"
    )
    return $code -eq 0
}

function Wait-Url([string]$Url, [string]$Name, [string]$LogFile) {
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Url $Url) { return }
        Start-Sleep -Milliseconds 500
    }
    if (Test-Path -LiteralPath "$LogFile.error") {
        Get-Content -LiteralPath "$LogFile.error" -Tail 30
    }
    throw "$Name failed to start. See $LogFile.error"
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
        $launcher = Get-PythonLauncher
        Write-Info "Creating a native Windows Python environment..."
        $code = Invoke-Native $launcher.File @($launcher.Args + @("-m", "venv", $VenvDir))
        if ($code -ne 0) { throw "Unable to create the Python virtual environment." }
    }

    if (!(Test-BackendEnvironment)) {
        Write-Info "Installing backend dependencies..."
        $pipArgs = @(
            "-m", "pip", "install",
            "--disable-pip-version-check",
            "--prefer-binary",
            "-r", $Requirements
        )
        $code = Invoke-Native $VenvPython $pipArgs
        if ($code -ne 0) {
            Write-Info "Default package source failed; retrying with the official PyPI source..."
            $code = Invoke-Native $VenvPython @(
                $pipArgs + @("-i", "https://pypi.org/simple")
            )
        }
        if ($code -ne 0) {
            Write-Info "Official PyPI failed; retrying with the Tsinghua mirror..."
            $code = Invoke-Native $VenvPython @(
                $pipArgs + @("-i", "https://pypi.tuna.tsinghua.edu.cn/simple")
            )
        }
        if ($code -ne 0) {
            throw @"
Backend dependency installation failed.

This is usually a Python package index or proxy problem, not a WSL problem.
Try one of these commands, then run start-windows.cmd again:

  .venv\Scripts\python.exe -m pip install --prefer-binary -r requirements.txt
  .venv\Scripts\python.exe -m pip install --prefer-binary -r requirements.txt -i https://pypi.org/simple
  .venv\Scripts\python.exe -m pip install --prefer-binary -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
"@
        }
        if (!(Test-BackendEnvironment)) {
            throw "Backend packages were installed, but the application import check failed."
        }
    }

    Assert-Node
    if (!(Test-Path -LiteralPath (Join-Path $Root "web\node_modules"))) {
        Write-Info "Installing frontend dependencies..."
        Push-Location (Join-Path $Root "web")
        try {
            $code = Invoke-Native "npm.cmd" @("ci")
            if ($code -ne 0) { throw "Frontend dependency installation failed." }
        } finally {
            Pop-Location
        }
    }
}

function Start-Services {
    if (!(Test-BackendEnvironment) -or
        !(Test-Path -LiteralPath (Join-Path $Root "web\node_modules"))) {
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
        $backend = Start-Process -FilePath $VenvPython `
            -ArgumentList @("-m", "uvicorn", "server.main:app", "--host", $backendHost, "--port", $backendPort) `
            -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.error"
        Set-Content -LiteralPath $BackendPid -Value $backend.Id
        Wait-Url $backendUrl "Backend" $BackendLog
    }

    if (!(Test-Url $frontendUrl)) {
        Write-Info "Starting frontend..."
        $env:QUANT_BACKEND_PORT = $backendPort
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
