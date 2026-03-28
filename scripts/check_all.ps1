# scripts/check_all.ps1
# Usage: from repo root, with venv activated:
#   powershell -ExecutionPolicy Bypass -File .\scripts\check_all.ps1
# or
#   .\scripts\check_all.ps1

param(
  [string]$LogsPath = "aaps_emulator\data\logs",
  [string]$CacheOut = "data\cache",
  [string]$LogFile = "scripts/check_all.log"
)

# Start logging
if (-not (Test-Path (Split-Path $LogFile))) {
  New-Item -ItemType Directory -Path (Split-Path $LogFile) -Force | Out-Null
}
if (Test-Path $LogFile) { Remove-Item $LogFile -Force }
Start-Transcript -Path $LogFile -Force

Write-Host "=== CHECK ALL START ===" -ForegroundColor Cyan
Write-Host "Working dir: $(Get-Location)"
Write-Host "Python: $(python --version 2>&1)"
Write-Host "Pip: $(pip -V 2>&1)"
Write-Host ""

function ExitOnError($code, $msg) {
  if ($code -ne 0) {
    Write-Host "ERROR: $msg (exit code $code)" -ForegroundColor Red
    Stop-Transcript
    exit $code
  }
}

# 1) Run pre-commit (if available)
Write-Host "`n1) Running pre-commit hooks..." -ForegroundColor Yellow
pre-commit run --all-files
ExitOnError $LASTEXITCODE "pre-commit failed"

# 2) Run ruff via python -m ruff if ruff not in PATH
Write-Host "`n2) Running ruff check (python -m ruff)..." -ForegroundColor Yellow
python -m ruff check . 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "ruff reported issues. Please fix or allow pre-commit to auto-fix." -ForegroundColor Red
  ExitOnError $LASTEXITCODE "ruff check failed"
}

# 3) Run tests
Write-Host "`n3) Running pytest..." -ForegroundColor Yellow
pytest -q
ExitOnError $LASTEXITCODE "pytest failed"

# 4) Generate inputs from logs
Write-Host "`n4) Generating inputs from logs..." -ForegroundColor Yellow
python -m aaps_emulator.tools.generate_inputs_from_logs $LogsPath --out $CacheOut
ExitOnError $LASTEXITCODE "generate_inputs_from_logs failed"

# 5) Validate project (if validate_all exists)
Write-Host "`n5) Running project validation..." -ForegroundColor Yellow
python -m aaps_emulator.tools.validate_all
if ($LASTEXITCODE -ne 0) {
  Write-Host "Validation returned non-zero exit code." -ForegroundColor Red
  ExitOnError $LASTEXITCODE "validate_all failed"
}

# 6) Smoke check first generated JSON
Write-Host "`n6) Smoke check first generated JSON..." -ForegroundColor Yellow
$files = Get-ChildItem -Path $CacheOut -Filter "inputs_before_algo_block_*.json" -File -ErrorAction SilentlyContinue | Sort-Object Name
if (-not $files) {
  Write-Host "No generated inputs found in $CacheOut" -ForegroundColor Red
  ExitOnError 2 "No generated inputs"
}
$sample = $files[0].FullName
Write-Host "Sample file: $sample"
Get-Content $sample -TotalCount 80

Write-Host "`nAll checks passed." -ForegroundColor Green
Stop-Transcript
exit 0
