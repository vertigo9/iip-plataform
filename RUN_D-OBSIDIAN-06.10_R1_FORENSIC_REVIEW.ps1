# ==============================================================================
# D-OBSIDIAN-06.10 R1 — CANDIDATE FORENSIC REVIEW
# ==============================================================================
# READ-ONLY / NON-DESTRUCTIVE
#
# Objetivos:
#   1. Carregar os outputs mais recentes do D-OBSIDIAN-06.9 R1.
#   2. Auditar os REMOVE-CANDIDATE.
#   3. Auditar grupos HAS-CANONICAL.
#   4. Auditar REVIEW-DUPLICATE.
#   5. Verificar referências textuais.
#   6. Calcular existência, tamanho e SHA256.
#   7. Aplicar invariantes de proteção.
#   8. Gerar evidências forenses.
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
$ReportsRoot = Join-Path $Repo "reports"
$SourceDir = Join-Path $ReportsRoot "D-OBSIDIAN-06.9-R1"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $ReportsRoot "D-OBSIDIAN-06.10-R1"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R1 — CANDIDATE FORENSIC REVIEW"
Write-Host "================================================================================"
Write-Host "Repository : $Repo"
Write-Host "Source     : $SourceDir"
Write-Host "Output     : $OutDir"
Write-Host "Timestamp  : $Timestamp"
Write-Host ""
Write-Host "READ-ONLY / NON-DESTRUCTIVE"
Write-Host "================================================================================"
Write-Host ""

# ------------------------------------------------------------------------------
# 01. SOURCE FILES
# ------------------------------------------------------------------------------

$DecisionFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$CanonicalFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_CANONICALIZATION_*.csv" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$DuplicateGroupFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$CandidateFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$CriticalReferenceFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_CRITICAL_REFERENCES_*.csv" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$SummaryFile = Get-ChildItem -LiteralPath $SourceDir -File `
    -Filter "D-OBSIDIAN-06.9_R1_SUMMARY_*.txt" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$RequiredFiles = @(
    $DecisionFile
    $CanonicalFile
    $DuplicateGroupFile
    $CandidateFile
    $CriticalReferenceFile
)

foreach ($Required in $RequiredFiles) {
    if (-not $Required) {
        throw "Arquivo obrigatório do D-OBSIDIAN-06.9 não encontrado."
    }
}

Write-Host "Decision Matrix : $($DecisionFile.Name)"
Write-Host "Canonicalization: $($CanonicalFile.Name)"
Write-Host "Duplicate Groups : $($DuplicateGroupFile.Name)"
Write-Host "D Candidates     : $($CandidateFile.Name)"
Write-Host "Critical Refs    : $($CriticalReferenceFile.Name)"
Write-Host ""

# ------------------------------------------------------------------------------
# 02. LOAD CSV
# ------------------------------------------------------------------------------

$DecisionRows = @(Import-Csv -LiteralPath $DecisionFile.FullName)
$CanonicalRows = @(Import-Csv -LiteralPath $CanonicalFile.FullName)
$DuplicateGroups = @(Import-Csv -LiteralPath $DuplicateGroupFile.FullName)
$CandidateRows = @(Import-Csv -LiteralPath $CandidateFile.FullName)
$CriticalRows = @(Import-Csv -LiteralPath $CriticalReferenceFile.FullName)

Write-Host "Loaded:"
Write-Host "  Decision Matrix : $($DecisionRows.Count)"
Write-Host "  Canonicalization: $($CanonicalRows.Count)"
Write-Host "  Duplicate Groups : $($DuplicateGroups.Count)"
Write-Host "  D Candidates     : $($CandidateRows.Count)"
Write-Host "  Critical Refs    : $($CriticalRows.Count)"
Write-Host ""

# ------------------------------------------------------------------------------
# 03. PROTECTION POLICY
# ------------------------------------------------------------------------------

$ProtectedPrefixes = @(
    "data/",
    "vault/",
    "archive/",
    "tests/intelligence/",
    "tests/integration/"
)

$ProtectedExact = @(
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py"
)

function Normalize-RepoPath {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    $P = $Path.Trim()
    $P = $P -replace "\\", "/"

    # Remove repository absolute prefix when present
    $RepoNormalized = $Repo -replace "\\", "/"
    if ($P.StartsWith($RepoNormalized, [System.StringComparison]::OrdinalIgnoreCase)) {
        $P = $P.Substring($RepoNormalized.Length).TrimStart("/")
    }

    return $P.TrimStart("./")
}

function Get-ProtectionClass {
    param(
        [string]$Path
    )

    $P = Normalize-RepoPath $Path

    if ([string]::IsNullOrWhiteSpace($P)) {
        return "UNKNOWN"
    }

    foreach ($Exact in $ProtectedExact) {
        if ($P.Equals($Exact, [System.StringComparison]::OrdinalIgnoreCase)) {
            return "PROTECTED-CRITICAL"
        }
    }

    foreach ($Prefix in $ProtectedPrefixes) {
        if ($P.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return "PROTECTED"
        }
    }

    return "NORMAL"
}

function Resolve-RepoFile {
    param(
        [string]$Path
    )

    $P = Normalize-RepoPath $Path

    if ([string]::IsNullOrWhiteSpace($P)) {
        return $null
    }

    $Full = Join-Path $Repo ($P -replace "/", "\")

    if (Test-Path -LiteralPath $Full -PathType Leaf) {
        return Get-Item -LiteralPath $Full
    }

    return $null
}

# ------------------------------------------------------------------------------
# 04. FORENSIC RESULT LISTS
# ------------------------------------------------------------------------------

$ForensicCandidates = [System.Collections.Generic.List[object]]::new()
$ForensicCanonical = [System.Collections.Generic.List[object]]::new()
$ForensicReview = [System.Collections.Generic.List[object]]::new()
$InvariantResults = [System.Collections.Generic.List[object]]::new()

# ------------------------------------------------------------------------------
# 05. REFERENCE SEARCH FUNCTION
# ------------------------------------------------------------------------------

$SearchRoots = @(
    (Join-Path $Repo "src"),
    (Join-Path $Repo "tests"),
    (Join-Path $Repo "scripts"),
    (Join-Path $Repo "reports"),
    (Join-Path $Repo "archive"),
    (Join-Path $Repo "vault"),
    (Join-Path $Repo "README.md"),
    (Join-Path $Repo "pyproject.toml")
)

function Find-TextReferences {
    param(
        [string]$RepoRelativePath
    )

    $Normalized = Normalize-RepoPath $RepoRelativePath
    $Name = Split-Path $Normalized -Leaf

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return @()
    }

    $Matches = [System.Collections.Generic.List[object]]::new()

    foreach ($Root in $SearchRoots) {

        if (-not (Test-Path -LiteralPath $Root)) {
            continue
        }

        try {
            $Files = if ((Get-Item -LiteralPath $Root).PSIsContainer) {
                Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue
            }
            else {
                Get-Item -LiteralPath $Root
            }

            foreach ($F in $Files) {

                # Ignore generated binary/archive formats for textual search.
                if ($F.Extension -in @(
                    ".zip",".7z",".rar",".exe",".dll",".pdb",
                    ".png",".jpg",".jpeg",".gif",".webp",
                    ".pdf",".xlsx",".xls",".docx",".pptx"
                )) {
                    continue
                }

                try {
                    $Found = Select-String `
                        -LiteralPath $F.FullName `
                        -Pattern [regex]::Escape($Name) `
                        -SimpleMatch:$false `
                        -ErrorAction SilentlyContinue

                    foreach ($M in $Found) {
                        $Matches.Add([PSCustomObject]@{
                            ReferencingFile = Normalize-RepoPath $F.FullName
                            LineNumber      = $M.LineNumber
                            Line            = ($M.Line.Trim())
                        })
                    }
                }
                catch {
                    # Read-only audit: unreadable files do not abort the whole scan.
                }
            }
        }
        catch {
        }
    }

    return @($Matches)
}

# ------------------------------------------------------------------------------
# 06. REMOVE-CANDIDATE FORENSIC REVIEW
# ------------------------------------------------------------------------------

$RemoveCandidates = @(
    $DecisionRows |
        Where-Object {
            $_.Decision -eq "REMOVE-CANDIDATE"
        }
)

Write-Host "REMOVE-CANDIDATE records: $($RemoveCandidates.Count)"
Write-Host ""

foreach ($Row in $RemoveCandidates) {

    $Path = Normalize-RepoPath $Row.Path
    $Item = Resolve-RepoFile $Path
    $Protection = Get-ProtectionClass $Path

    $Exists = $null -ne $Item
    $Size = $null
    $Hash = $null

    if ($Item) {
        $Size = $Item.Length

        try {
            $Hash = (Get-FileHash -LiteralPath $Item.FullName -Algorithm SHA256).Hash
        }
        catch {
            $Hash = "HASH_ERROR"
        }
    }

    $Refs = @(Find-TextReferences $Path)

    $ProvisionalAction = "NEEDS-APPROVAL"

    if ($Protection -ne "NORMAL") {
        $ProvisionalAction = "DO-NOT-TOUCH"
    }
    elseif ($Refs.Count -gt 0) {
        $ProvisionalAction = "BLOCKED-BY-REFERENCE"
    }

    $ForensicCandidates.Add([PSCustomObject]@{
        Path               = $Path
        Class              = $Row.Class
        Type               = $Row.Type
        Policy             = $Row.Policy
        Decision           = $Row.Decision
        Protection         = $Protection
        Exists             = $Exists
        SizeBytes          = $Size
        SHA256             = $Hash
        ReferenceCount     = $Refs.Count
        References         = (($Refs | ForEach-Object {
            "$($_.ReferencingFile):$($_.LineNumber)"
        }) -join " | ")
        ProvisionalAction  = $ProvisionalAction
        Reason             = $Row.Reason
    })

    Write-Host "[$Protection] $Path"
    Write-Host "  Exists     : $Exists"
    Write-Host "  Size       : $Size"
    Write-Host "  SHA256     : $Hash"
    Write-Host "  References : $($Refs.Count)"
    Write-Host "  Action     : $ProvisionalAction"
    Write-Host ""
}

# ------------------------------------------------------------------------------
# 07. CANONICALIZATION FORENSIC REVIEW
# ------------------------------------------------------------------------------

$CanonicalGroups = @(
    $DuplicateGroups |
        Where-Object {
            $_.Status -eq "HAS-CANONICAL" -or
            $_.CanonicalStatus -eq "HAS-CANONICAL"
        }
)

Write-Host "HAS-CANONICAL groups: $($CanonicalGroups.Count)"
Write-Host ""

foreach ($Group in $CanonicalGroups) {

    $Hash = $Group.Hash
    $GroupRows = @(
        $CanonicalRows |
            Where-Object {
                $_.Hash -eq $Hash
            }
    )

    if ($GroupRows.Count -eq 0) {
        $ForensicCanonical.Add([PSCustomObject]@{
            Hash              = $Hash
            GroupSize         = $Group.GroupSize
            CanonicalPath     = ""
            DuplicatePath     = ""
            CanonicalExists   = $false
            DuplicateExists   = $false
            CanonicalClass    = ""
            DuplicateClass    = ""
            CanonicalDecision = ""
            DuplicateDecision = ""
            Protection        = "UNKNOWN"
            ProvisionalAction = "REVIEW-MISSING-CANONICAL-DATA"
        })

        continue
    }

    $CanonicalPath = ($GroupRows |
        Where-Object {
            $_.CanonicalPath -and
            $_.Path -eq $_.CanonicalPath
        } |
        Select-Object -First 1).Path

    if ([string]::IsNullOrWhiteSpace($CanonicalPath)) {
        $CanonicalPath = ($GroupRows |
            Where-Object {
                $_.CanonicalStatus -match "CANONICAL"
            } |
            Select-Object -First 1).Path
    }

    if ([string]::IsNullOrWhiteSpace($CanonicalPath)) {
        $CanonicalPath = ($GroupRows | Select-Object -First 1).CanonicalPath
    }

    $CanonicalItem = Resolve-RepoFile $CanonicalPath
    $CanonicalProtection = Get-ProtectionClass $CanonicalPath

    foreach ($R in $GroupRows) {

        $DuplicatePath = Normalize-RepoPath $R.Path

        if ($DuplicatePath -eq $CanonicalPath) {
            continue
        }

        $DuplicateItem = Resolve-RepoFile $DuplicatePath
        $DuplicateProtection = Get-ProtectionClass $DuplicatePath

        $Protection = if (
            $CanonicalProtection -ne "NORMAL" -or
            $DuplicateProtection -ne "NORMAL"
        ) {
            "PROTECTED"
        }
        else {
            "NORMAL"
        }

        $Action = "REVIEW"

        if ($Protection -ne "NORMAL") {
            $Action = "DO-NOT-TOUCH"
        }
        elseif (-not $CanonicalItem) {
            $Action = "REVIEW-MISSING-CANONICAL"
        }
        elseif (-not $DuplicateItem) {
            $Action = "REVIEW-MISSING-DUPLICATE"
        }
        else {
            $Action = "REVIEW-CANONICAL-DUPLICATE"
        }

        $ForensicCanonical.Add([PSCustomObject]@{
            Hash              = $Hash
            GroupSize         = $Group.GroupSize
            CanonicalPath     = $CanonicalPath
            DuplicatePath     = $DuplicatePath
            CanonicalExists   = ($null -ne $CanonicalItem)
            DuplicateExists   = ($null -ne $DuplicateItem)
            CanonicalClass    = $R.Class
            DuplicateClass    = $R.Class
            CanonicalDecision = $R.Decision
            DuplicateDecision = $R.Decision
            Protection        = $Protection
            ProvisionalAction = $Action
        })
    }
}

# ------------------------------------------------------------------------------
# 08. REVIEW-DUPLICATE FORENSIC REVIEW
# ------------------------------------------------------------------------------

$ReviewRows = @(
    $DecisionRows |
        Where-Object {
            $_.Decision -eq "REVIEW-DUPLICATE"
        }
)

Write-Host "REVIEW-DUPLICATE records: $($ReviewRows.Count)"
Write-Host ""

foreach ($Row in $ReviewRows) {

    $Path = Normalize-RepoPath $Row.Path
    $Protection = Get-ProtectionClass $Path
    $Item = Resolve-RepoFile $Path
    $Refs = @(Find-TextReferences $Path)

    $Action = "REVIEW"

    if ($Protection -ne "NORMAL") {
        $Action = "DO-NOT-TOUCH"
    }
    elseif ($Row.Type -match "BRIDGE|PATCH") {
        $Action = "TRANSITION-REVIEW"
    }
    elseif ($Refs.Count -gt 0) {
        $Action = "REVIEW-BLOCKED-BY-REFERENCE"
    }

    $ForensicReview.Add([PSCustomObject]@{
        Path              = $Path
        Class             = $Row.Class
        Type              = $Row.Type
        Policy            = $Row.Policy
        Decision          = $Row.Decision
        Protection        = $Protection
        Exists            = ($null -ne $Item)
        ReferenceCount    = $Refs.Count
        References        = (($Refs | ForEach-Object {
            "$($_.ReferencingFile):$($_.LineNumber)"
        }) -join " | ")
        ProvisionalAction = $Action
    })
}

# ------------------------------------------------------------------------------
# 09. INVARIANT CHECKS
# ------------------------------------------------------------------------------

function Add-Invariant {
    param(
        [string]$Name,
        [bool]$Pass,
        [string]$Detail
    )

    $InvariantResults.Add([PSCustomObject]@{
        Invariant = $Name
        Status    = if ($Pass) { "PASS" } else { "FAIL" }
        Detail    = $Detail
    })
}

# Protected paths must never appear as actionable REMOVE-CANDIDATE.
$ProtectedRemove = @(
    $ForensicCandidates |
        Where-Object {
            $_.Protection -ne "NORMAL" -and
            $_.ProvisionalAction -ne "DO-NOT-TOUCH"
        }
)

Add-Invariant `
    "PROTECTED_REMOVE_GUARD" `
    ($ProtectedRemove.Count -eq 0) `
    "Protected REMOVE-CANDIDATE rows with actionable state: $($ProtectedRemove.Count)"

# Critical intelligence files must exist.
foreach ($Critical in $ProtectedExact) {

    $CriticalItem = Resolve-RepoFile $Critical

    Add-Invariant `
        "CRITICAL_EXISTS::$Critical" `
        ($null -ne $CriticalItem) `
        "Critical component exists: $($null -ne $CriticalItem)"
}

# Protected directory trees must exist.
foreach ($Prefix in $ProtectedPrefixes) {

    $Directory = Join-Path $Repo ($Prefix.TrimEnd("/") -replace "/", "\")

    Add-Invariant `
        "PROTECTED_TREE::$Prefix" `
        (Test-Path -LiteralPath $Directory -PathType Container) `
        "Protected tree exists: $(Test-Path -LiteralPath $Directory -PathType Container)"
}

# No REMOVE-CANDIDATE duplicate group is allowed.
$RemoveGroups = @(
    $DuplicateGroups |
        Where-Object {
            $_.Status -match "REMOVE"
        }
)

Add-Invariant `
    "NO_REMOVE_DUPLICATE_GROUP" `
    ($RemoveGroups.Count -eq 0) `
    "Duplicate groups classified for removal: $($RemoveGroups.Count)"

# 06.9 source reports must exist.
foreach ($Source in $RequiredFiles) {

    Add-Invariant `
        "SOURCE_REPORT::$($Source.Name)" `
        (Test-Path -LiteralPath $Source.FullName -PathType Leaf) `
        "Source report present."
}

# ------------------------------------------------------------------------------
# 10. WRITE FORENSIC OUTPUTS
# ------------------------------------------------------------------------------

$CandidateCsv = Join-Path $OutDir "D-OBSIDIAN-06.10_R1_REMOVE_CANDIDATES_$Timestamp.csv"
$CanonicalCsv = Join-Path $OutDir "D-OBSIDIAN-06.10_R1_CANONICAL_FORENSICS_$Timestamp.csv"
$ReviewCsv = Join-Path $OutDir "D-OBSIDIAN-06.10_R1_REVIEW_DUPLICATES_$Timestamp.csv"
$InvariantCsv = Join-Path $OutDir "D-OBSIDIAN-06.10_R1_INVARIANTS_$Timestamp.csv"
$SummaryTxt = Join-Path $OutDir "D-OBSIDIAN-06.10_R1_SUMMARY_$Timestamp.txt"

$ForensicCandidates |
    Export-Csv -LiteralPath $CandidateCsv -NoTypeInformation -Encoding UTF8

$ForensicCanonical |
    Export-Csv -LiteralPath $CanonicalCsv -NoTypeInformation -Encoding UTF8

$ForensicReview |
    Export-Csv -LiteralPath $ReviewCsv -NoTypeInformation -Encoding UTF8

$InvariantResults |
    Export-Csv -LiteralPath $InvariantCsv -NoTypeInformation -Encoding UTF8

$Gate = $true

foreach ($Invariant in $InvariantResults) {
    if ($Invariant.Status -eq "FAIL") {
        $Gate = $false
    }
}

$Summary = [System.Collections.Generic.List[string]]::new()

$Summary.Add("D-OBSIDIAN-06.10 R1 — CANDIDATE FORENSIC REVIEW")
$Summary.Add("Repository: $Repo")
$Summary.Add("Timestamp: $Timestamp")
$Summary.Add("")
$Summary.Add("SOURCE:")
$Summary.Add("  Decision Matrix : $($DecisionFile.Name)")
$Summary.Add("  Canonicalization: $($CanonicalFile.Name)")
$Summary.Add("  Duplicate Groups : $($DuplicateGroupFile.Name)")
$Summary.Add("  D Candidates     : $($CandidateFile.Name)")
$Summary.Add("  Critical Refs    : $($CriticalReferenceFile.Name)")
$Summary.Add("")
$Summary.Add("FORENSIC COUNTS:")
$Summary.Add("  REMOVE-CANDIDATE : $($ForensicCandidates.Count)")
$Summary.Add("  HAS-CANONICAL    : $($ForensicCanonical.Count)")
$Summary.Add("  REVIEW-DUPLICATE : $($ForensicReview.Count)")
$Summary.Add("")
$Summary.Add("PROVISIONAL ACTIONS — REMOVE CANDIDATES:")

foreach ($Group in ($ForensicCandidates | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($Group.Name): $($Group.Count)")
}

$Summary.Add("")
$Summary.Add("PROVISIONAL ACTIONS — CANONICAL:")
foreach ($Group in ($ForensicCanonical | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($Group.Name): $($Group.Count)")
}

$Summary.Add("")
$Summary.Add("PROVISIONAL ACTIONS — REVIEW:")
foreach ($Group in ($ForensicReview | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($Group.Name): $($Group.Count)")
}

$Summary.Add("")
$Summary.Add("INVARIANTS:")

foreach ($Invariant in $InvariantResults) {
    $Summary.Add("  [$($Invariant.Status)] $($Invariant.Invariant) — $($Invariant.Detail)")
}

$Summary.Add("")
$Summary.Add("SAFETY:")
$Summary.Add("  No files removed.")
$Summary.Add("  No files moved.")
$Summary.Add("  No files renamed.")
$Summary.Add("  No file contents modified.")
$Summary.Add("  No git add.")
$Summary.Add("  No git commit.")
$Summary.Add("  No git restore.")
$Summary.Add("  No git reset.")
$Summary.Add("  No git clean.")
$Summary.Add("")

if ($Gate) {
    $Summary.Add("FORENSIC GATE: PASS")
}
else {
    $Summary.Add("FORENSIC GATE: FAIL")
}

$Summary |
    Set-Content -LiteralPath $SummaryTxt -Encoding UTF8

# ------------------------------------------------------------------------------
# 11. CONSOLE REPORT
# ------------------------------------------------------------------------------

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R1 — RESULTADO"
Write-Host "================================================================================"

Write-Host ""
Write-Host "REMOVE-CANDIDATE : $($ForensicCandidates.Count)"
Write-Host "HAS-CANONICAL    : $($ForensicCanonical.Count)"
Write-Host "REVIEW-DUPLICATE : $($ForensicReview.Count)"

Write-Host ""
Write-Host "INVARIANTS:"
foreach ($Invariant in $InvariantResults) {

    if ($Invariant.Status -eq "PASS") {
        Write-Host "[PASS] $($Invariant.Invariant)" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $($Invariant.Invariant)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "OUTPUTS:"
Write-Host "  $CandidateCsv"
Write-Host "  $CanonicalCsv"
Write-Host "  $ReviewCsv"
Write-Host "  $InvariantCsv"
Write-Host "  $SummaryTxt"

Write-Host ""

if ($Gate) {
    Write-Host "================================================================================"
    Write-Host "FORENSIC GATE: PASS" -ForegroundColor Green
    Write-Host "================================================================================"
}
else {
    Write-Host "================================================================================"
    Write-Host "FORENSIC GATE: FAIL" -ForegroundColor Red
    Write-Host "================================================================================"
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.10 R1 concluído em modo READ-ONLY."
