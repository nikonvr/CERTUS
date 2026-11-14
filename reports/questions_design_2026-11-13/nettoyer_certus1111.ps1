# Nettoyage du dossier certus1111 (2026-11-13). A lancer depuis la racine du depot :
#   .\reports\questions_design_2026-11-13\nettoyer_certus1111.ps1         # apercu
#   .\reports\questions_design_2026-11-13\nettoyer_certus1111.ps1 -Apply  # application
# Rien de suivi par git n'est touche ; rien sous reports\ n'est touche. Ce qui n'est pas jetable est DEPLACE hors du
# depot, dans ..\certus1111_hors_depot\2026-11-13\, jamais efface.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'

$root = (git rev-parse --show-toplevel).Trim() -replace '/', '\'
Set-Location $root
if (-not (Test-Path (Join-Path $root 'CLAUDE.md'))) { throw "Pas a la racine de CERTUS : $root" }
$outside = Join-Path (Split-Path $root -Parent) 'certus1111_hors_depot\2026-11-13'

function Do-It([string]$what, [scriptblock]$action) {
    if ($Apply) { & $action; Write-Host "FAIT    $what" } else { Write-Host "A FAIRE $what" }
}

function Same-Text([string]$a, [string]$b) {
    if (-not (Test-Path $a) -or -not (Test-Path $b)) { return $false }
    ((Get-Content -Raw $a) -replace "`r`n", "`n") -ceq ((Get-Content -Raw $b) -replace "`r`n", "`n")
}

function Move-Outside([string]$relativePath) {
    $source = (Resolve-Path -LiteralPath (Join-Path $root $relativePath)).Path
    if (-not $source.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors du depot : $source"
    }
    $destination = [IO.Path]::GetFullPath((Join-Path $outside $relativePath))
    if (-not $destination.StartsWith($outside + '\', [StringComparison]::OrdinalIgnoreCase) -or
        (Test-Path -LiteralPath $destination)) {
        throw "Destination invalide ou deja occupee : $destination"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Move-Item -LiteralPath $source -Destination $destination
}

# 1. Le worktree de la passation : ses six fichiers STRAT sont dans l'arbre principal. On ne le retire que s'ils y
#    sont a l'identique (fins de ligne mises a part) ; sinon on s'arrete pour ce point et on le dit.
$wt = Join-Path $root '.claude\worktrees\reprise-057fcd'
$strat = @('certus\core\certus_strat_leviers.py', 'certus\core\certus_strat_local_search.py',
           'certus\ui\certus_strat_ui_state.py', 'certus\workers\certus_strat_workers_local_search.py',
           'tests\unit\test_certus_strat_json_loading.py', 'tests\unit\test_strat_local_search.py')
if (Test-Path $wt) {
    $differ = @($strat | Where-Object { -not (Same-Text (Join-Path $wt $_) (Join-Path $root $_)) })
    $worktreeChanges = @(git -C $wt diff --name-only HEAD)
    $unexpected = @($worktreeChanges | Where-Object { ($_ -replace '/', '\') -notin $strat })
    $other = @(git -C $wt -c core.quotepath=false ls-files --others --exclude-standard)
    if ($differ.Count -eq 0 -and $unexpected.Count -eq 0 -and $other.Count -eq 0) {
        Do-It "retirer le worktree .claude\worktrees\reprise-057fcd (ses 6 fichiers STRAT sont dans l'arbre principal)" {
            $resolvedWorktree = (Resolve-Path -LiteralPath $wt).Path
            if ($resolvedWorktree -ne (Join-Path $root '.claude\worktrees\reprise-057fcd')) {
                throw "Worktree hors du chemin attendu : $resolvedWorktree"
            }
            $kept = @(git -C $wt -c core.quotepath=false ls-files --others --ignored --exclude-standard |
                Where-Object { $_ -notmatch '(^|/)(__pycache__|\.pytest_cache|\.ruff_cache|\.hypothesis)(/|$)' })
            foreach ($rel in $kept) { Move-Outside (Join-Path '.claude\worktrees\reprise-057fcd' $rel) }
            git worktree remove --force $resolvedWorktree
            if ($LASTEXITCODE -ne 0) { throw 'Impossible de retirer le worktree de reprise.' }
        }
        Do-It "supprimer la branche claude/reprise-057fcd si elle est fusionnee (git branch -d refuse sinon)" {
            $ErrorActionPreference = 'Continue'
            git branch -d claude/reprise-057fcd *> $null
            if ($LASTEXITCODE -ne 0) { Write-Host "        branche gardee : non fusionnee" }
        }
    } else {
        Write-Host "GARDE   worktree reprise-057fcd : fichiers a examiner $((@($differ) + $unexpected + $other) -join ', ')"
    }
}
Do-It "git worktree prune (entrees de .git\worktrees dont le dossier n'existe plus)" { git worktree prune }

# 2. Hors du depot, sans rien perdre : brouillons de session, copie de CLAUDE.md, documents du concours OIC 2016
#    (oeuvres de tiers : jamais dans un depot public).
$move = @('scratch', 'CLAUDE.md.bak', 'OIC 2016 Contest Description.pdf', 'OIC 2016 Manufacturing Contest.xls',
          'OIC_2016_Design_Problems.pdf', 'certus\physics\design_resonances.py.bak_lossy_20261107',
          'tests\oracle\test_design_complex_wavelength_resonances.py.bak_lossy_20261107')
foreach ($item in $move) {
    $src = Join-Path $root $item
    if ((Test-Path $src) -and -not (git ls-files -- $item)) {
        Do-It "deplacer $item vers $outside" {
            Move-Outside $item
        }
    }
}

# 3. Journaux historiques a la racine et dossiers vides. Seulement ce que git ne suit pas.
$tracked = @(git ls-files) | ForEach-Object { $_ -replace '/', '\' }
Get-ChildItem -LiteralPath $root -File | Where-Object {
    ($_.Extension -in '.log', '.jsonl' -or $_.Name -eq 'test_log') -and ($tracked -notcontains $_.Name)
} | ForEach-Object { $name = $_.Name; Do-It "archiver $name" { Move-Outside $name } }
foreach ($dir in 'tmp', 'snom', 'bonne mere', 'invalid_dir') {
    $d = Join-Path $root $dir
    if ((Test-Path $d) -and -not (Get-ChildItem -LiteralPath $d -Force)) {
        Do-It "effacer le dossier vide $dir" { Remove-Item -LiteralPath $d -Force }
    }
}

Write-Host ''
git worktree list
git status --short
if (-not $Apply) { Write-Host "`nRien n'a ete fait. Relancer avec -Apply pour appliquer." }
