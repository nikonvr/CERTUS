$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Path $PSScriptRoot -Parent
Set-Location -Path $repoRoot

Write-Host "[CERTUS] frozen build starting..."
Write-Host "[CERTUS] repo: $repoRoot"

python -m PyInstaller --noconfirm "certus_hub.spec"
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[CERTUS] frozen build FAILED (exit=$exitCode)"
    exit $exitCode
}

Write-Host "[CERTUS] frozen build PASSED"
exit 0
