function Get-RateR3SHA256([string]$Path) {
    $rateR3Hasher=[System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($rateR3Hasher.ComputeHash([System.IO.File]::ReadAllBytes($Path)))).Replace('-','').ToLowerInvariant()
    } finally {
        $rateR3Hasher.Dispose()
    }
}
$rateR3Directory=Split-Path -Parent $PSScriptRoot
$rateR3Observed=Get-RateR3SHA256 (Join-Path $rateR3Directory 'control\etat.json')
$rateR3Expected=(Get-Content -Raw -LiteralPath (Join-Path $rateR3Directory 'audit_control.json')|ConvertFrom-Json).state_sha256
if($rateR3Observed -ne $rateR3Expected){throw 'Control audit hash mismatch'}
$rateR3Proof=[ordered]@{verdict='GO';powershell=$PSVersionTable.PSVersion.ToString();actual_control_hash=$rateR3Observed;expected_control_hash=$rateR3Expected;physics_measured=$false}
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'verify_resume_sha.json'),($rateR3Proof|ConvertTo-Json),[System.Text.UTF8Encoding]::new($false))
$rateR3Proof|ConvertTo-Json
