<#
.SYNOPSIS
    Build and push Docker images for Razorpay AI Finance Controller.
.DESCRIPTION
    Builds backend and frontend Docker images separately and pushes them to Docker Hub.
.PARAMETER Username
    Docker Hub username/namespace (defaults to archisman2006).
.PARAMETER Tag
    Docker image tag (defaults to latest).
.PARAMETER Push
    Whether to push to Docker Hub after building.
#>
param(
    [string]$Username = "archisman2006",
    [string]$Tag = "latest",
    [switch]$Push = $true
)

$ErrorActionPreference = "Stop"

$BackendImage = "${Username}/razorpay-backend:${Tag}"
$FrontendImage = "${Username}/razorpay-frontend:${Tag}"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Building Docker Images" -ForegroundColor Cyan
Write-Host " Backend : $BackendImage" -ForegroundColor Cyan
Write-Host " Frontend: $FrontendImage" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Build Backend
Write-Host "`n[1/2] Building Backend Docker image..." -ForegroundColor Green
docker build -t $BackendImage -f backend/Dockerfile .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend build failed!"
    exit 1
}

# 2. Build Frontend
Write-Host "`n[2/2] Building Frontend Docker image..." -ForegroundColor Green
docker build -t $FrontendImage -f frontend/Dockerfile ./frontend
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend build failed!"
    exit 1
}

Write-Host "`nSuccessfully built both images!" -ForegroundColor Green

# 3. Push to Docker Hub if requested
if ($Push) {
    Write-Host "`n====================================================" -ForegroundColor Cyan
    Write-Host " Pushing to Docker Hub" -ForegroundColor Cyan
    Write-Host "====================================================" -ForegroundColor Cyan

    Write-Host "`nPushing $BackendImage..." -ForegroundColor Green
    docker push $BackendImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push $BackendImage to Docker Hub!"
        exit 1
    }

    Write-Host "`nPushing $FrontendImage..." -ForegroundColor Green
    docker push $FrontendImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push $FrontendImage to Docker Hub!"
        exit 1
    }

    Write-Host "`nSuccessfully pushed all images to Docker Hub!" -ForegroundColor Green
}
