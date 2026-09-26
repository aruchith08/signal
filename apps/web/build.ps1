# SIGNAL 📡 — Web App Build Script
# Syncs code to local high-speed SSD cache to avoid Google Drive VFS locks, compiles, and copies dist.

$SourceDir = $PSScriptRoot
$CacheDir = "C:\Users\aruch\.signal_cache\signal_web"

Write-Host "📡 Building SIGNAL Web Terminal..." -ForegroundColor Cyan

# 1. Ensure cache directory exists
if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
}

# 2. Copy source files to SSD cache
Write-Host "→ Syncing source files to SSD workspace..." -ForegroundColor Gray
Copy-Item -Recurse -Force "$SourceDir\src" "$CacheDir"
Copy-Item -Force "$SourceDir\package.json", "$SourceDir\vite.config.ts", "$SourceDir\tsconfig.json", "$SourceDir\tailwind.config.js", "$SourceDir\postcss.config.js", "$SourceDir\index.html" -Destination "$CacheDir"

# 3. Check if node_modules exists in cache
if (-not (Test-Path "$CacheDir\node_modules")) {
    Write-Host "→ Installing npm dependencies on SSD..." -ForegroundColor Gray
    Push-Location $CacheDir
    npm install
    Pop-Location
}

# 4. Run Vite build
Write-Host "→ Running TypeScript compiler and Vite bundler..." -ForegroundColor Gray
Push-Location $CacheDir
npm run build
$BuildResult = $LASTEXITCODE
Pop-Location

if ($BuildResult -eq 0) {
    Write-Host "→ Copying production bundle to apps/web/dist..." -ForegroundColor Gray
    if (-not (Test-Path "$SourceDir\dist")) {
        New-Item -ItemType Directory -Force -Path "$SourceDir\dist" | Out-Null
    }
    Copy-Item -Recurse -Force "$CacheDir\dist\*" "$SourceDir\dist"
    Write-Host "✓ SIGNAL Web Application built successfully!" -ForegroundColor Green
    Write-Host "  Static files available at: $SourceDir\dist" -ForegroundColor DarkGray
    Write-Host "  FastAPI Web Mount: http://localhost:8000/app" -ForegroundColor Cyan
    exit 0
}

Write-Host "✗ Build failed with exit code $BuildResult" -ForegroundColor Red
exit $BuildResult
