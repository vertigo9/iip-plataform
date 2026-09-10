# D-OBSIDIAN-06.10 R4 — CANONICAL TRIANGULATION AUDIT
# READ-ONLY / NON-DESTRUCTIVE

$ErrorActionPreference = "Stop"
$Repo = (Get-Location).Path
$SourceDir = Join-Path $Repo "reports\D-OBSIDIAN-06.9-R1"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Repo "reports\D-OBSIDIAN-06.10-R4"
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

function Get-LatestFile {
    param([string]$Pattern)
    $F = Get-ChildItem -LiteralPath $SourceDir -File -Filter $Pattern |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $F) { throw "Fonte não encontrada: $Pattern" }
    return $F
}

function Get-Value {
    param([object]$Row,[string[]]$Names)
    foreach ($Name in $Names) {
        $P = $Row.PSObject.Properties |
            Where-Object { $_.Name.Equals($Name,[System.StringComparison]::OrdinalIgnoreCase) } |
            Select-Object -First 1
        if ($P) {
            $V = [string]$P.Value
            if (-not [string]::IsNullOrWhiteSpace($V)) { return $V.Trim() }
        }
    }
    return ""
}

function Normalize-Path {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
    $P = $Path.Trim() -replace "\\", "/"
    $RepoNorm = $Repo -replace "\\", "/"
    if ($P.StartsWith($RepoNorm,[System.StringComparison]::OrdinalIgnoreCase)) {
        $P = $P.Substring($RepoNorm.Length).TrimStart("/")
    }
    return $P.TrimStart("./")
}

function Resolve-File {
    param([string]$Path)
    $P = Normalize-Path $Path
    if ([string]::IsNullOrWhiteSpace($P)) { return $null }
    $Full = Join-Path $Repo ($P -replace "/", "\")
    if (Test-Path -LiteralPath $Full -PathType Leaf) { return Get-Item -LiteralPath $Full }
    return $null
}

function Get-Protection {
    param([string]$Path)
    $P = Normalize-Path $Path
    $Exact = @(
        "src/iip/intelligence/metric_identity.py",
        "src/iip/intelligence/metric_persistence.py",
        "src/iip/intelligence/metric_persistence_adapter.py"
    )
    $Prefixes = @("data/","vault/","archive/","tests/intelligence/","tests/integration/")
    foreach ($X in $Exact) {
        if ($P.Equals($X,[System.StringComparison]::OrdinalIgnoreCase)) { return "PROTECTED-CRITICAL" }
    }
    foreach ($X in $Prefixes) {
        if ($P.StartsWith($X,[System.StringComparison]::OrdinalIgnoreCase)) { return "PROTECTED" }
    }
    return "NORMAL"
}

function Add-Check {
    param([System.Collections.Generic.List[object]]$List,[string]$Name,[int]$Expected,[int]$Actual)
    $Status = "FAIL"
    if ($Expected -eq $Actual) { $Status = "PASS" }
    $List.Add([PSCustomObject]@{
        Check=$Name; Expected=$Expected; Actual=$Actual; Status=$Status
    })
}

$DecisionFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv"
$CanonicalFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_CANONICALIZATION_*.csv"
$DuplicateFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv"
$CandidateFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv"

$DecisionRows = @(Import-Csv $DecisionFile.FullName)
$CanonicalRows = @(Import-Csv $CanonicalFile.FullName)
$DuplicateRows = @(Import-Csv $DuplicateFile.FullName)
$CandidateRows = @(Import-Csv $CandidateFile.FullName)

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R4 — CANONICAL TRIANGULATION AUDIT"
Write-Host "================================================================================"
Write-Host "Repository : $Repo"
Write-Host "Output     : $OutDir"
Write-Host "READ-ONLY / NON-DESTRUCTIVE"
Write-Host ""
Write-Host "INPUT"
Write-Host "  Decision       : $($DecisionRows.Count)"
Write-Host "  Canonical      : $($CanonicalRows.Count)"
Write-Host "  Duplicate      : $($DuplicateRows.Count)"
Write-Host "  Candidates     : $($CandidateRows.Count)"
Write-Host ""

$StatusValues = @(
    $CanonicalRows | ForEach-Object { Get-Value $_ @("CanonicalStatus") } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
)
Write-Host "DISTINCT CanonicalStatus VALUES"
foreach ($V in $StatusValues) {
    $Count = @($CanonicalRows | Where-Object { (Get-Value $_ @("CanonicalStatus")) -eq $V }).Count
    Write-Host "  [$Count] $V"
}

$GroupDecisionValues = @(
    $DuplicateRows | ForEach-Object { Get-Value $_ @("GroupDecision") } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
)
Write-Host ""
Write-Host "DISTINCT GroupDecision VALUES"
foreach ($V in $GroupDecisionValues) {
    $Count = @($DuplicateRows | Where-Object { (Get-Value $_ @("GroupDecision")) -eq $V }).Count
    Write-Host "  [$Count] $V"
}

$CanonicalGroups = @(
    $DuplicateRows | Where-Object { (Get-Value $_ @("GroupDecision")) -eq "HAS-CANONICAL" }
)
$CanonicalGroupHashes = @(
    $CanonicalGroups | ForEach-Object { Get-Value $_ @("Hash") } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
)

Write-Host ""
Write-Host "GROUP CLASSIFICATION"
Write-Host "  HAS-CANONICAL rows   : $($CanonicalGroups.Count)"
Write-Host "  HAS-CANONICAL hashes : $($CanonicalGroupHashes.Count)"

$Triangulation = [System.Collections.Generic.List[object]]::new()

foreach ($Group in $CanonicalGroups) {
    $Hash = Get-Value $Group @("Hash")
    $MatchingCanonical = @($CanonicalRows | Where-Object { (Get-Value $_ @("Hash")) -eq $Hash })
    $MatchingDecision = @($DecisionRows | Where-Object { (Get-Value $_ @("Hash")) -eq $Hash })

    $CanonicalStatuses = @(
        $MatchingCanonical | ForEach-Object { Get-Value $_ @("CanonicalStatus") } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
    )
    $CanonicalPaths = @(
        $MatchingCanonical | ForEach-Object {
            Normalize-Path (Get-Value $_ @("CanonicalPath"))
        } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
    )
    $Paths = @(
        $MatchingCanonical | ForEach-Object {
            Normalize-Path (Get-Value $_ @("Path"))
        } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
    )

    $ExistingPaths = [System.Collections.Generic.List[string]]::new()
    $ProtectedPaths = [System.Collections.Generic.List[string]]::new()
    foreach ($Path in $Paths) {
        if ($null -ne (Resolve-File $Path)) { $ExistingPaths.Add($Path) }
        if ((Get-Protection $Path) -ne "NORMAL") { $ProtectedPaths.Add($Path) }
    }

    $StatusText = $CanonicalStatuses -join " | "
    $CanonicalPathText = $CanonicalPaths -join " | "
    $StatusHasCanonical = $StatusText -match "CANONICAL"
    $PathPresent = $CanonicalPaths.Count -gt 0

    $EvidenceConsistent = (
        $MatchingCanonical.Count -gt 0 -and
        ($StatusHasCanonical -or $PathPresent) -and
        $MatchingDecision.Count -gt 0
    )

    $Triangulation.Add([PSCustomObject]@{
        Hash=$Hash
        GroupSize=(Get-Value $Group @("GroupSize"))
        GroupDecision=(Get-Value $Group @("GroupDecision"))
        CanonicalRows=$MatchingCanonical.Count
        CanonicalStatus=$StatusText
        CanonicalPath=$CanonicalPathText
        Paths=($Paths -join " || ")
        ExistingPaths=($ExistingPaths -join " || ")
        ProtectedPaths=($ProtectedPaths -join " || ")
        DecisionRows=$MatchingDecision.Count
        CanonicalStatusHasWord=$StatusHasCanonical
        CanonicalPathPresent=$PathPresent
        EvidenceConsistent=$EvidenceConsistent
    })
}

$Checks = [System.Collections.Generic.List[object]]::new()

$RemoveCount = @(
    $DecisionRows | Where-Object { (Get-Value $_ @("Decision")) -eq "REMOVE-CANDIDATE" }
).Count
$ReviewCount = @(
    $DecisionRows | Where-Object { (Get-Value $_ @("Decision")) -eq "REVIEW-DUPLICATE" }
).Count
$EvidenceFailures = @(
    $Triangulation | Where-Object { $_.EvidenceConsistent -eq $false }
).Count
$CoverageFailures = @(
    $CanonicalGroupHashes | Where-Object {
        $H = $_
        @($Triangulation | Where-Object { $_.Hash -eq $H }).Count -eq 0
    }
).Count
$InvalidGroupDecision = @(
    $Triangulation | Where-Object { $_.GroupDecision -ne "HAS-CANONICAL" }
).Count

Add-Check $Checks "DECISION_TOTAL" 910 $DecisionRows.Count
Add-Check $Checks "CANONICALIZATION_TOTAL" 910 $CanonicalRows.Count
Add-Check $Checks "DUPLICATE_GROUPS_TOTAL" 430 $DuplicateRows.Count
Add-Check $Checks "REMOVE_CANDIDATE" 2 $RemoveCount
Add-Check $Checks "REVIEW_DUPLICATE" 126 $ReviewCount
Add-Check $Checks "HAS_CANONICAL_GROUPS" 63 $CanonicalGroupHashes.Count
Add-Check $Checks "CANONICAL_TRIANGULATION_EVIDENCE" 0 $EvidenceFailures
Add-Check $Checks "CANONICAL_GROUP_COVERAGE" 0 $CoverageFailures
Add-Check $Checks "TRIANGULATION_GROUP_DECISION_GUARD" 0 $InvalidGroupDecision

foreach ($Critical in @(
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py"
)) {
    $Actual = 0
    if ($null -ne (Resolve-File $Critical)) { $Actual = 1 }
    Add-Check $Checks "CRITICAL_EXISTS::$Critical" 1 $Actual
}

foreach ($Tree in @("data","vault","archive","tests/intelligence","tests/integration")) {
    $Full = Join-Path $Repo ($Tree -replace "/", "\")
    $Actual = 0
    if (Test-Path -LiteralPath $Full -PathType Container) { $Actual = 1 }
    Add-Check $Checks "PROTECTED_TREE::$Tree" 1 $Actual
}

$StatusOut = Join-Path $OutDir "D-OBSIDIAN-06.10_R4_STATUS_VALUES_$Timestamp.csv"
$GroupDecisionOut = Join-Path $OutDir "D-OBSIDIAN-06.10_R4_GROUP_DECISION_VALUES_$Timestamp.csv"
$TriangulationOut = Join-Path $OutDir "D-OBSIDIAN-06.10_R4_CANONICAL_TRIANGULATION_$Timestamp.csv"
$ChecksOut = Join-Path $OutDir "D-OBSIDIAN-06.10_R4_COMPLETENESS_$Timestamp.csv"
$SummaryOut = Join-Path $OutDir "D-OBSIDIAN-06.10_R4_SUMMARY_$Timestamp.txt"

$StatusRows = [System.Collections.Generic.List[object]]::new()
foreach ($V in $StatusValues) {
    $StatusRows.Add([PSCustomObject]@{
        Value=$V
        Count=@($CanonicalRows | Where-Object { (Get-Value $_ @("CanonicalStatus")) -eq $V }).Count
    })
}
$GroupDecisionRows = [System.Collections.Generic.List[object]]::new()
foreach ($V in $GroupDecisionValues) {
    $GroupDecisionRows.Add([PSCustomObject]@{
        Value=$V
        Count=@($DuplicateRows | Where-Object { (Get-Value $_ @("GroupDecision")) -eq $V }).Count
    })
}

$StatusRows | Export-Csv $StatusOut -NoTypeInformation -Encoding UTF8
$GroupDecisionRows | Export-Csv $GroupDecisionOut -NoTypeInformation -Encoding UTF8
$Triangulation | Export-Csv $TriangulationOut -NoTypeInformation -Encoding UTF8
$Checks | Export-Csv $ChecksOut -NoTypeInformation -Encoding UTF8

$Failures = @($Checks | Where-Object { $_.Status -eq "FAIL" })
$Gate = ($Failures.Count -eq 0)

$Summary = [System.Collections.Generic.List[string]]::new()
$Summary.Add("D-OBSIDIAN-06.10 R4 — CANONICAL TRIANGULATION AUDIT")
$Summary.Add("")
$Summary.Add("READ-ONLY / NON-DESTRUCTIVE")
$Summary.Add("")
$Summary.Add("INPUT")
$Summary.Add("Decision rows: $($DecisionRows.Count)")
$Summary.Add("Canonical rows: $($CanonicalRows.Count)")
$Summary.Add("Duplicate groups: $($DuplicateRows.Count)")
$Summary.Add("Candidates: $($CandidateRows.Count)")
$Summary.Add("")
$Summary.Add("OBSERVED CanonicalStatus VALUES")
foreach ($R in $StatusRows) { $Summary.Add("  [$($R.Count)] $($R.Value)") }
$Summary.Add("")
$Summary.Add("OBSERVED GroupDecision VALUES")
foreach ($R in $GroupDecisionRows) { $Summary.Add("  [$($R.Count)] $($R.Value)") }
$Summary.Add("")
$Summary.Add("CANONICAL POPULATION")
$Summary.Add("Expected HAS-CANONICAL groups: 63")
$Summary.Add("Detected HAS-CANONICAL groups: $($CanonicalGroupHashes.Count)")
$Summary.Add("")
$Summary.Add("TRIANGULATION")
$Summary.Add("Triangulated groups: $($Triangulation.Count)")
$Summary.Add("Evidence failures: $EvidenceFailures")
$Summary.Add("Canonical groups without triangulation: $CoverageFailures")
$Summary.Add("")
$Summary.Add("CHECKS")
foreach ($C in $Checks) {
    $Summary.Add("[$($C.Status)] $($C.Check) Expected=$($C.Expected) Actual=$($C.Actual)")
}
$Summary.Add("")
$Summary.Add("SAFETY")
$Summary.Add("No files removed.")
$Summary.Add("No files moved.")
$Summary.Add("No files renamed.")
$Summary.Add("No source contents modified.")
$Summary.Add("No git add.")
$Summary.Add("No git commit.")
$Summary.Add("No git restore.")
$Summary.Add("No git reset.")
$Summary.Add("No git clean.")
$Summary.Add("")
if ($Gate) {
    $Summary.Add("FORENSIC COMPLETENESS GATE: PASS")
} else {
    $Summary.Add("FORENSIC COMPLETENESS GATE: FAIL")
}
$Summary | Set-Content $SummaryOut -Encoding UTF8

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R4 — RESULTADO"
Write-Host "================================================================================"
Write-Host ""
Write-Host "OBSERVED CanonicalStatus VALUES"
foreach ($R in $StatusRows) { Write-Host "  [$($R.Count)] $($R.Value)" }
Write-Host ""
Write-Host "OBSERVED GroupDecision VALUES"
foreach ($R in $GroupDecisionRows) { Write-Host "  [$($R.Count)] $($R.Value)" }
Write-Host ""
Write-Host "CANONICAL POPULATION"
Write-Host "  Expected HAS-CANONICAL groups : 63"
Write-Host "  Detected HAS-CANONICAL groups : $($CanonicalGroupHashes.Count)"
Write-Host ""
foreach ($C in $Checks) {
    if ($C.Status -eq "PASS") {
        Write-Host "[PASS] $($C.Check) Expected=$($C.Expected) Actual=$($C.Actual)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($C.Check) Expected=$($C.Expected) Actual=$($C.Actual)" -ForegroundColor Red
    }
}
Write-Host ""
if ($Gate) {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: PASS"
    Write-Host "================================================================================"
} else {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: FAIL"
    Write-Host "================================================================================"
}
Write-Host ""
Write-Host "D-OBSIDIAN-06.10 R4 concluído em modo READ-ONLY."
