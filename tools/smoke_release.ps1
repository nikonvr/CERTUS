$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Path $PSScriptRoot -Parent
Set-Location -Path $repoRoot

$env:QT_QPA_PLATFORM = "offscreen"

Write-Host "[CERTUS] smoke release (offscreen) starting..."
Write-Host "[CERTUS] repo: $repoRoot"
Write-Host "[CERTUS] QT_QPA_PLATFORM=$env:QT_QPA_PLATFORM"

python -m pytest "tests/unit/test_gui_smoke.py" "tests/integration/test_smoke_certus_index_spline.py" -q --tb=short --no-cov
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[CERTUS] smoke release FAILED (exit=$exitCode)"
    exit $exitCode
}

Write-Host "[CERTUS] smoke release PASSED"
exit 0
