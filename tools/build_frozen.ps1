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

# PyInstaller exits 0 even when it has left something out: the build is done when the executable is there.
$exe = Join-Path $repoRoot "dist\CERTUS_HUB\CERTUS_HUB.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host "[CERTUS] frozen build FAILED: $exe was not produced"
    exit 1
}

Write-Host "[CERTUS] frozen build PASSED ($exe)"
exit 0
