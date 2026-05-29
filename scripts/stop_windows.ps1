# stop_windows.ps1 — Stop and remove the FinAlly container (Windows PowerShell)
# NOTE: The Docker volume (finally-data) is NOT removed — your data persists.

$ErrorActionPreference = "Stop"

$ContainerName = "finally"

# ──────────────────────────────────────────────────────────────────────────────
# Check prerequisites
# ──────────────────────────────────────────────────────────────────────────────
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────────
# Stop running container
# ──────────────────────────────────────────────────────────────────────────────
$RunningContainers = docker ps --format "{{.Names}}" 2>$null
if ($RunningContainers -match "^$ContainerName$") {
    Write-Host "Stopping container '$ContainerName'..."
    docker stop $ContainerName | Out-Null
} else {
    Write-Host "Container '$ContainerName' is not running."
}

# ──────────────────────────────────────────────────────────────────────────────
# Remove container (but NOT the volume)
# ──────────────────────────────────────────────────────────────────────────────
$AllContainers = docker ps -a --format "{{.Names}}" 2>$null
if ($AllContainers -match "^$ContainerName$") {
    Write-Host "Removing container '$ContainerName'..."
    docker rm $ContainerName | Out-Null
}

Write-Host "FinAlly stopped. Your portfolio data is preserved in the 'finally-data' volume."
Write-Host "Run .\scripts\start_windows.ps1 to start again."
