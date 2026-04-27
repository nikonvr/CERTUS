$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Path $PSScriptRoot -Parent
Set-Location -Path $repoRoot

$env:QT_QPA_PLATFORM = "offscreen"

Write-Host "[CERTUS] smoke release (offscreen) starting..."
Write-Host "[CERTUS] repo: $repoRoot"
Write-Host "[CERTUS] QT_QPA_PLATFORM=$env:QT_QPA_PLATFORM"

python "tests/smoke_test_suite.py"
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[CERTUS] smoke release FAILED (exit=$exitCode)"
    exit $exitCode
}

Write-Host "[CERTUS] smoke release PASSED"
exit 0
