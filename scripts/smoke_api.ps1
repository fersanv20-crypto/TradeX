# Quick connectivity check for the TradeX FastAPI backend (paper mode).
# Usage: .\scripts\smoke_api.ps1 [-BaseUrl http://127.0.0.1:8000]
param([string]$BaseUrl = "http://127.0.0.1:8000")

$ErrorActionPreference = "Stop"
function Test-Get($path) {
  $u = "$BaseUrl$path"
  try {
    $r = Invoke-RestMethod -Uri $u -Method Get
    Write-Host "OK GET $path" -ForegroundColor Green
    return $r
  } catch {
    Write-Host "FAIL GET $path :: $_" -ForegroundColor Red
    throw
  }
}

Write-Host "TradeX API smoke test -> $BaseUrl" -ForegroundColor Cyan
Test-Get "/health" | Out-Null
Test-Get "/price" | Out-Null
Test-Get "/portfolio" | Out-Null
Test-Get "/auto-trading" | Out-Null
Test-Get "/bot-status" | Out-Null
Test-Get "/auto-trading/logs?limit=3" | Out-Null
Test-Get "/trades?limit=5" | Out-Null
Test-Get "/performance" | Out-Null
Write-Host "All checks passed." -ForegroundColor Green
