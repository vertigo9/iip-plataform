$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.7_BATCH_CLEANUP_INVENTORY.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W {
    param([string]$Text)
    Write-Host $Text
    Add-Content $Report $Text -Encoding ASCII
}

W "D-OBSIDIAN-06.7 BATCH CLEANUP - PRE-MOVE SAFETY INVENTORY"
W ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss"))
W "READ-ONLY. No files will be moved, deleted, or modified."
W "Protected baseline: 96.64%"
W ""

$rules = @(
    @{ Name="OPS_SCRIPTS"; Pattern="^(RUN_|APPLY_).*\.(ps1|py)$" },
    @{ Name="OPS_TOOLS"; Pattern="^(COLLECT_IIP_SOURCE|PATCH_CSV_TEST)\.(ps1|py)$" },
    @{ Name="LOGS"; Pattern="\.(log|txt)$" },
    @{ Name="BACKUPS"; Pattern="(\.bak\d*|_old$|backup)" },
    @{ Name="GENERATED"; Pattern="^(\.coverage)$" },
    @{ Name="PATCH_ARTIFACTS"; Pattern="patria_.*(patch|corrigido).*" }
)

W "=== ROOT CANDIDATES ==="
$rootFiles = Get-ChildItem . -File -Force

foreach ($rule in $rules) {
    W ""
    W ("[" + $rule.Name + "]")
    $matches = $rootFiles | Where-Object { $_.Name -match $rule.Pattern } | Sort-Object Name
    if ($matches.Count -eq 0) {
        W "(none)"
    } else {
        $matches | ForEach-Object { W $_.Name }
    }
}

W ""
W "=== IN-SOURCE BACKUP CANDIDATES ==="
Get-ChildItem .\src -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "(\.bak\d*|_old$|backup)" } |
    Sort-Object FullName |
    ForEach-Object { W $_.FullName }

W ""
W "=== PYTHON IMPORT REFERENCES TO ROOT SCRIPTS/PATCHES ==="
$patterns = @(
    "APPLY_[A-Za-z0-9_]+",
    "RUN_[A-Za-z0-9_]+",
    "patria_harvester_patch",
    "patria_corrigido",
    "setup_iip",
    "COLLECT_IIP_SOURCE"
)

$hits = Get-ChildItem .\src,.\tests -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern $patterns -SimpleMatch:$false

if ($hits) {
    $hits | ForEach-Object {
        W ("{0}:{1}:{2}" -f $_.Path,$_.LineNumber,$_.Line.Trim())
    }
} else {
    W "(no references found)"
}

W ""
W "=== GIT TRACKING SUMMARY ==="
git status --short 2>&1 | Tee-Object $Report -Append

W ""
W "=== GITIGNORE CURRENT RULES ==="
if (Test-Path .\.gitignore) {
    Get-Content .\.gitignore | ForEach-Object { W $_ }
}

W ""
W "STATUS: PRE-MOVE SAFETY INVENTORY COMPLETE"
W ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
W "No changes made."

Write-Host ""
Write-Host "Relatorio: $Report"
exit 0
