# start_windows.ps1 — Build and run the FinAlly container (Windows PowerShell)
# Usage: .\scripts\start_windows.ps1 [-Build]
#   -Build  Force a Docker image rebuild even if it already exists

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ContainerName = "finally"
$ImageName     = "finally"
$Port          = 8000
$AppUrl        = "http://localhost:$Port"
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot   = Split-Path -Parent $ScriptDir

# ──────────────────────────────────────────────────────────────────────────────
# Check prerequisites
# ──────────────────────────────────────────────────────────────────────────────
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH."
    exit 1
}

$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Warning ".env file not found at $EnvFile"
    Write-Warning "Copy .env.example to .env and fill in your API keys."
    Write-Warning "Continuing anyway — the simulator will be used for market data."
}

# ──────────────────────────────────────────────────────────────────────────────
# Handle already-running container
# ──────────────────────────────────────────────────────────────────────────────
$RunningContainers = docker ps --format "{{.Names}}" 2>$null
if ($RunningContainers -match "^$ContainerName$") {
    Write-Host "Container '$ContainerName' is already running."
    Write-Host "  App URL: $AppUrl"
    Write-Host "  To stop: .\scripts\stop_windows.ps1"
    Write-Host "  To rebuild and restart: .\scripts\stop_windows.ps1; .\scripts\start_windows.ps1 -Build"
    exit 0
}

# Remove stopped container with same name if it exists
$AllContainers = docker ps -a --format "{{.Names}}" 2>$null
if ($AllContainers -match "^$ContainerName$") {
    Write-Host "Removing stopped container '$ContainerName'..."
    docker rm $ContainerName | Out-Null
}

# ──────────────────────────────────────────────────────────────────────────────
# Build image if needed
# ──────────────────────────────────────────────────────────────────────────────
$ImageExists = docker images -q $ImageName 2>$null

if ($Build -or [string]::IsNullOrEmpty($ImageExists)) {
    Write-Host "Building Docker image '$ImageName'..."
    docker build -t $ImageName $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed."
        exit 1
    }
} else {
    Write-Host "Docker image '$ImageName' already exists. Use -Build to rebuild."
}

# ──────────────────────────────────────────────────────────────────────────────
# Run the container
# ──────────────────────────────────────────────────────────────────────────────
Write-Host "Starting FinAlly..."

$DockerArgs = @(
    "run", "-d",
    "--name", $ContainerName,
    "-v", "finally-data:/app/db",
    "-p", "${Port}:${Port}"
)

if (Test-Path $EnvFile) {
    $DockerArgs += "--env-file"
    $DockerArgs += $EnvFile
}

$DockerArgs += $ImageName

& docker @DockerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start container."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────────
# Wait for the container to be healthy
# ──────────────────────────────────────────────────────────────────────────────
Write-Host "Waiting for FinAlly to start..."
$Attempts    = 0
$MaxAttempts = 30
$HealthUrl   = "$AppUrl/api/health"

do {
    Start-Sleep -Seconds 1
    $Attempts++
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($Response.StatusCode -eq 200) { break }
    } catch {
        # Not ready yet
    }
    if ($Attempts -ge $MaxAttempts) {
        Write-Error "FinAlly did not start within 30 seconds. Check logs: docker logs $ContainerName"
        exit 1
    }
} while ($true)

Write-Host ""
Write-Host "FinAlly is running!"
Write-Host "  App URL:  $AppUrl"
Write-Host "  Logs:     docker logs -f $ContainerName"
Write-Host "  Stop:     .\scripts\stop_windows.ps1"
Write-Host ""

# Open browser
Start-Process $AppUrl
