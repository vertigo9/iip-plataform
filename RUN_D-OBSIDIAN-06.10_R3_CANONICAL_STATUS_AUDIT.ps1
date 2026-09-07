# ==============================================================================
# D-OBSIDIAN-06.10 R3 — CANONICAL STATUS FORENSIC AUDIT
# ==============================================================================
# READ-ONLY / NON-DESTRUCTIVE
#
# Regra canônica:
#   CanonicalStatus == HAS-CANONICAL
#
# NÃO executa:
#   Remove-Item
#   Move-Item
#   Rename-Item
#   git add
#   git commit
#   git restore
#   git reset
#   git clean
# ==============================================================================

$ErrorActionPreference = "Stop"

$Repo = (Get-Location).Path
$SourceDir = Join-Path $Repo "reports\D-OBSIDIAN-06.9-R1"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Repo "reports\D-OBSIDIAN-06.10-R3"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

function Get-LatestFile {
    param([string]$Pattern)

    $F = Get-ChildItem -LiteralPath $SourceDir -File -Filter $Pattern |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $F) {
        throw "Fonte não encontrada: $Pattern"
    }

    return $F
}

function Get-PropertyValue {
    param(
        [object]$Row,
        [string[]]$Names
    )

    foreach ($Name in $Names) {

        $Prop = $Row.PSObject.Properties |
            Where-Object {
                $_.Name.Equals(
                    $Name,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            } |
            Select-Object -First 1

        if ($Prop) {
            $Value = [string]$Prop.Value

            if (-not [string]::IsNullOrWhiteSpace($Value)) {
                return $Value.Trim()
            }
        }
    }

    return ""
}

function Normalize-Path {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    $P = $Path.Trim() -replace "\\", "/"
    $RepoNorm = $Repo -replace "\\", "/"

    if ($P.StartsWith(
        $RepoNorm,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        $P = $P.Substring($RepoNorm.Length).TrimStart("/")
    }

    return $P.TrimStart("./")
}

function Resolve-RepoFile {
    param([string]$Path)

    $P = Normalize-Path $Path

    if ([string]::IsNullOrWhiteSpace($P)) {
        return $null
    }

    $Full = Join-Path $Repo ($P -replace "/", "\")

    if (Test-Path -LiteralPath $Full -PathType Leaf) {
        return Get-Item -LiteralPath $Full
    }

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

    $Prefixes = @(
        "data/",
        "vault/",
        "archive/",
        "tests/intelligence/",
        "tests/integration/"
    )

    foreach ($X in $Exact) {
        if ($P.Equals(
            $X,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            return "PROTECTED-CRITICAL"
        }
    }

    foreach ($X in $Prefixes) {
        if ($P.StartsWith(
            $X,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            return "PROTECTED"
        }
    }

    return "NORMAL"
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
Write-Host "D-OBSIDIAN-06.10 R3 — CANONICAL STATUS FORENSIC AUDIT"
Write-Host "================================================================================"
Write-Host "Repository : $Repo"
Write-Host "Output     : $OutDir"
Write-Host ""
Write-Host "READ-ONLY / NON-DESTRUCTIVE"
Write-Host ""

# ------------------------------------------------------------------------------
# SCHEMA AUDIT
# ------------------------------------------------------------------------------

$SchemaRows = [System.Collections.Generic.List[object]]::new()

foreach ($Pair in @(
    @("DECISION", $DecisionRows),
    @("CANONICAL", $CanonicalRows),
    @("DUPLICATE", $DuplicateRows),
    @("CANDIDATE", $CandidateRows)
)) {

    $Name = $Pair[0]
    $Rows = @($Pair[1])

    $Headers = @()

    if ($Rows.Count -gt 0) {
        $Headers = @(
            $Rows[0].PSObject.Properties.Name
        )
    }

    foreach ($Header in $Headers) {
        $SchemaRows.Add([PSCustomObject]@{
            Dataset = $Name
            Header  = $Header
        })
    }
}

# CanonicalStatus must exist.
$CanonicalStatusHeader = @(
    $SchemaRows |
        Where-Object {
            $_.Dataset -eq "CANONICAL" -and
            $_.Header.Equals(
                "CanonicalStatus",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
)

$CanonicalPathHeader = @(
    $SchemaRows |
        Where-Object {
            $_.Dataset -eq "CANONICAL" -and
            $_.Header.Equals(
                "CanonicalPath",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
)

# ------------------------------------------------------------------------------
# POPULATION RECONSTRUCTION
# ------------------------------------------------------------------------------

$RemoveRows = @(
    $DecisionRows |
        Where-Object {
            (Get-PropertyValue $_ @("Decision")) -eq "REMOVE-CANDIDATE"
        }
)

$ReviewRows = @(
    $DecisionRows |
        Where-Object {
            (Get-PropertyValue $_ @("Decision")) -eq "REVIEW-DUPLICATE"
        }
)

# AUTHORITATIVE CANONICAL FILTER.
$CanonicalStatusRows = @(
    $CanonicalRows |
        Where-Object {
            (Get-PropertyValue $_ @("CanonicalStatus")) -eq "HAS-CANONICAL"
        }
)

$CanonicalHashes = @(
    $CanonicalStatusRows |
        ForEach-Object {
            Get-PropertyValue $_ @("Hash")
        } |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        } |
        Sort-Object -Unique
)

Write-Host "INPUT"
Write-Host "  Decision rows       : $($DecisionRows.Count)"
Write-Host "  Canonical rows      : $($CanonicalRows.Count)"
Write-Host "  Duplicate groups    : $($DuplicateRows.Count)"
Write-Host "  Candidate rows      : $($CandidateRows.Count)"
Write-Host ""

Write-Host "CANONICAL STATUS"
Write-Host "  HAS-CANONICAL rows  : $($CanonicalStatusRows.Count)"
Write-Host "  HAS-CANONICAL groups: $($CanonicalHashes.Count)"
Write-Host ""

# ------------------------------------------------------------------------------
# CANONICAL FORENSICS
# ------------------------------------------------------------------------------

$CanonicalForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Hash in $CanonicalHashes) {

    $Rows = @(
        $CanonicalStatusRows |
            Where-Object {
                (Get-PropertyValue $_ @("Hash")) -eq $Hash
            }
    )

    $CanonicalPathValues = @(
        $Rows |
            ForEach-Object {
                Normalize-Path (
                    Get-PropertyValue $_ @("CanonicalPath")
                )
            } |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_)
            } |
            Sort-Object -Unique
    )

    $CanonicalPath = ""

    if ($CanonicalPathValues.Count -eq 1) {
        $CanonicalPath = $CanonicalPathValues[0]
    }
    elseif ($CanonicalPathValues.Count -gt 1) {
        $CanonicalPath = ($CanonicalPathValues -join " || ")
    }

    foreach ($Row in $Rows) {

        $Path = Normalize-Path (
            Get-PropertyValue $Row @("Path")
        )

        $CanonicalExplicit = Normalize-Path (
            Get-PropertyValue $Row @("CanonicalPath")
        )

        $Item = Resolve-RepoFile $Path
        $Protection = Get-Protection $Path

        $HashActual = ""

        if ($Item) {
            try {
                $HashActual = (
                    Get-FileHash `
                        -LiteralPath $Item.FullName `
                        -Algorithm SHA256
                ).Hash
            }
            catch {
                $HashActual = "HASH_ERROR"
            }
        }

        $CanonicalForensics.Add([PSCustomObject]@{
            Hash              = $Hash
            Path              = $Path
            Class             = Get-PropertyValue $Row @("Class")
            Type              = Get-PropertyValue $Row @("Type")
            Decision          = Get-PropertyValue $Row @("Decision")
            CanonicalStatus   = Get-PropertyValue $Row @("CanonicalStatus")
            CanonicalPath     = $CanonicalPath
            ExplicitCanonical = $CanonicalExplicit
            Exists            = ($null -ne $Item)
            Protection        = $Protection
            ActualSHA256      = $HashActual
            SourceSHA256      = $Hash
            HashMatch         = (
                -not [string]::IsNullOrWhiteSpace($HashActual) -and
                $HashActual.Equals(
                    $Hash,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            )
        })
    }
}

# ------------------------------------------------------------------------------
# REMOVE FORENSICS
# ------------------------------------------------------------------------------

$RemoveForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Row in $RemoveRows) {

    $Path = Normalize-Path (
        Get-PropertyValue $Row @("Path")
    )

    $Item = Resolve-RepoFile $Path
    $Protection = Get-Protection $Path

    $Action = "NEEDS-APPROVAL"

    if ($Protection -ne "NORMAL") {
        $Action = "DO-NOT-TOUCH"
    }
    elseif ($null -eq $Item) {
        $Action = "ALREADY-ABSENT"
    }

    $RemoveForensics.Add([PSCustomObject]@{
        Path              = $Path
        Class             = Get-PropertyValue $Row @("Class")
        Type              = Get-PropertyValue $Row @("Type")
        Decision          = Get-PropertyValue $Row @("Decision")
        Protection        = $Protection
        Exists            = ($null -ne $Item)
        ProvisionalAction = $Action
        Reason            = Get-PropertyValue $Row @("Reason")
    })
}

# ------------------------------------------------------------------------------
# REVIEW FORENSICS
# ------------------------------------------------------------------------------

$ReviewForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Row in $ReviewRows) {

    $Path = Normalize-Path (
        Get-PropertyValue $Row @("Path")
    )

    $Protection = Get-Protection $Path

    $Action = "REVIEW"

    if ($Protection -ne "NORMAL") {
        $Action = "DO-NOT-TOUCH"
    }

    $ReviewForensics.Add([PSCustomObject]@{
        Hash              = Get-PropertyValue $Row @("Hash")
        Path              = $Path
        GroupSize         = Get-PropertyValue $Row @("GroupSize")
        Class             = Get-PropertyValue $Row @("Class")
        Type              = Get-PropertyValue $Row @("Type")
        Policy            = Get-PropertyValue $Row @("Policy")
        Decision          = Get-PropertyValue $Row @("Decision")
        Protection        = $Protection
        Exists            = ($null -ne (Resolve-RepoFile $Path))
        ProvisionalAction = $Action
    })
}

# ------------------------------------------------------------------------------
# COMPLETENESS
# ------------------------------------------------------------------------------

$Completeness = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [int]$Expected,
        [int]$Actual
    )

    $Completeness.Add([PSCustomObject]@{
        Check    = $Name
        Expected = $Expected
        Actual   = $Actual
        Status   = if ($Expected -eq $Actual) { "PASS" } else { "FAIL" }
    })
}

Add-Check "DECISION_TOTAL" 910 $DecisionRows.Count
Add-Check "REMOVE_CANDIDATE" 2 $RemoveRows.Count
Add-Check "REVIEW_DUPLICATE" 126 $ReviewRows.Count
Add-Check "DUPLICATE_GROUPS" 430 $DuplicateRows.Count
Add-Check "CANONICAL_HAS_STATUS_ROWS" 63 $CanonicalStatusRows.Count
Add-Check "CANONICAL_HAS_STATUS_GROUPS" 63 $CanonicalHashes.Count

# ------------------------------------------------------------------------------
# PROTECTION
# ------------------------------------------------------------------------------

$ProtectedViolations = @(
    $CanonicalForensics |
        Where-Object {
            $_.Protection -ne "NORMAL" -and
            $_.Protection -notmatch "PROTECTED"
        }
)

$Completeness.Add([PSCustomObject]@{
    Check    = "PROTECTED_CANONICAL_GUARD"
    Expected = 0
    Actual   = $ProtectedViolations.Count
    Status   = if ($ProtectedViolations.Count -eq 0) {
        "PASS"
    } else {
        "FAIL"
    }
})

foreach ($Critical in @(
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py"
)) {

    $Exists = $null -ne (Resolve-RepoFile $Critical)

    $Completeness.Add([PSCustomObject]@{
        Check    = "CRITICAL_EXISTS::$Critical"
        Expected = 1
        Actual   = if ($Exists) { 1 } else { 0 }
        Status   = if ($Exists) { "PASS" } else { "FAIL" }
    })
}

foreach ($Tree in @(
    "data",
    "vault",
    "archive",
    "tests/intelligence",
    "tests/integration"
)) {

    $Full = Join-Path $Repo ($Tree -replace "/", "\")

    $Exists = Test-Path -LiteralPath $Full -PathType Container

    $Completeness.Add([PSCustomObject]@{
        Check    = "PROTECTED_TREE::$Tree"
        Expected = 1
        Actual   = if ($Exists) { 1 } else { 0 }
        Status   = if ($Exists) { "PASS" } else { "FAIL" }
    })
}

# ------------------------------------------------------------------------------
# GATE
# ------------------------------------------------------------------------------

$Failures = @(
    $Completeness |
        Where-Object {
            $_.Status -eq "FAIL"
        }
)

$Gate = ($Failures.Count -eq 0)

# ------------------------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------------------------

$SchemaOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_SCHEMA_AUDIT_$Timestamp.csv"

$CanonicalOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_CANONICAL_FORENSICS_$Timestamp.csv"

$RemoveOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_REMOVE_FORENSICS_$Timestamp.csv"

$ReviewOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_REVIEW_FORENSICS_$Timestamp.csv"

$CompleteOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_COMPLETENESS_$Timestamp.csv"

$SummaryOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R3_SUMMARY_$Timestamp.txt"

$SchemaRows |
    Export-Csv $SchemaOut -NoTypeInformation -Encoding UTF8

$CanonicalForensics |
    Export-Csv $CanonicalOut -NoTypeInformation -Encoding UTF8

$RemoveForensics |
    Export-Csv $RemoveOut -NoTypeInformation -Encoding UTF8

$ReviewForensics |
    Export-Csv $ReviewOut -NoTypeInformation -Encoding UTF8

$Completeness |
    Export-Csv $CompleteOut -NoTypeInformation -Encoding UTF8

$Summary = [System.Collections.Generic.List[string]]::new()

$Summary.Add("D-OBSIDIAN-06.10 R3 — CANONICAL STATUS FORENSIC AUDIT")
$Summary.Add("")
$Summary.Add("INPUT")
$Summary.Add("Decision rows: $($DecisionRows.Count)")
$Summary.Add("Canonical rows: $($CanonicalRows.Count)")
$Summary.Add("Duplicate groups: $($DuplicateRows.Count)")
$Summary.Add("Candidate rows: $($CandidateRows.Count)")
$Summary.Add("")
$Summary.Add("AUTHORITATIVE CANONICAL POPULATION")
$Summary.Add("CanonicalStatus=HAS-CANONICAL rows: $($CanonicalStatusRows.Count)")
$Summary.Add("CanonicalStatus=HAS-CANONICAL groups: $($CanonicalHashes.Count)")
$Summary.Add("")
$Summary.Add("EXPECTED")
$Summary.Add("Decision total: 910")
$Summary.Add("Remove candidate: 2")
$Summary.Add("Review duplicate: 126")
$Summary.Add("Duplicate groups: 430")
$Summary.Add("HAS-CANONICAL rows: 63")
$Summary.Add("HAS-CANONICAL groups: 63")
$Summary.Add("")
$Summary.Add("FAILURES: $($Failures.Count)")
$Summary.Add("")

foreach ($F in $Failures) {
    $Summary.Add(
        "[FAIL] $($F.Check) Expected=$($F.Expected) Actual=$($F.Actual)"
    )
}

$Summary.Add("")
$Summary.Add("SAFETY")
$Summary.Add("No files removed.")
$Summary.Add("No files moved.")
$Summary.Add("No files renamed.")
$Summary.Add("No source contents modified.")
$Summary.Add("No git add/commit/restore/reset/clean.")

$Summary.Add("")

if ($Gate) {
    $Summary.Add("FORENSIC COMPLETENESS GATE: PASS")
}
else {
    $Summary.Add("FORENSIC COMPLETENESS GATE: FAIL")
}

$Summary |
    Set-Content $SummaryOut -Encoding UTF8

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R3 — RESULTADO"
Write-Host "================================================================================"
Write-Host ""
Write-Host "Decision total      : $($DecisionRows.Count)"
Write-Host "REMOVE-CANDIDATE    : $($RemoveRows.Count)"
Write-Host "REVIEW-DUPLICATE    : $($ReviewRows.Count)"
Write-Host "DUPLICATE GROUPS    : $($DuplicateRows.Count)"
Write-Host "HAS-CANONICAL ROWS  : $($CanonicalStatusRows.Count)"
Write-Host "HAS-CANONICAL GROUPS: $($CanonicalHashes.Count)"
Write-Host ""

foreach ($C in $Completeness) {

    if ($C.Status -eq "PASS") {
        Write-Host "[PASS] $($C.Check) Expected=$($C.Expected) Actual=$($C.Actual)" `
            -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $($C.Check) Expected=$($C.Expected) Actual=$($C.Actual)" `
            -ForegroundColor Red
    }
}

Write-Host ""

if ($Gate) {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: PASS"
    Write-Host "================================================================================"
}
else {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: FAIL"
    Write-Host "================================================================================"
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.10 R3 concluído em modo READ-ONLY."
