# SIGNAL 📡 — Web App Dev Server Script
# Syncs code to SSD cache and starts Vite development server with API proxy.

$SourceDir = $PSScriptRoot
$CacheDir = "C:\Users\aruch\.signal_cache\signal_web"

Write-Host "📡 Launching SIGNAL Web Dev Server..." -ForegroundColor Cyan

if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
}

Write-Host "→ Syncing source files to SSD workspace..." -ForegroundColor Gray
Copy-Item -Recurse -Force "$SourceDir\src" "$CacheDir"
Copy-Item -Force "$SourceDir\package.json", "$SourceDir\vite.config.ts", "$SourceDir\tsconfig.json", "$SourceDir\tailwind.config.js", "$SourceDir\postcss.config.js", "$SourceDir\index.html" -Destination "$CacheDir"

Push-Location $CacheDir
npm run dev
Pop-Location
