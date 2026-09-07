$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"

$Manifest = Join-Path $Repo "reports\PCIP11_EXTRACTION_MANIFEST_0695_2R.csv"
$OutDir = Join-Path $Repo "reports"

$OutputCsv = Join-Path $OutDir "PCIP11_CONTENT_TRIAGE_0695_2R2.csv"
$OutputMd = Join-Path $OutDir "PCIP11_CONTENT_TRIAGE_0695_2R2.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.2R2 - PCIP11 CONTENT TRIAGE"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# 1. VALIDATE INPUT
# ============================================================

Write-Host "[1/7] Validating normalized manifest..."

if (-not (Test-Path $Manifest)) {
    throw "Normalized manifest not found: $Manifest"
}

$rows = Import-Csv $Manifest

Write-Host ("Manifest rows: " + $rows.Count)

# ============================================================
# 2. SELECT UNIQUE PHYSICAL DOCUMENTS
# ============================================================

Write-Host "[2/7] Selecting unique physical documents..."

$uniqueRows = @(
    $rows |
    Where-Object {
        $_.Duplicate_Status -eq "UNIQUE" -or
        $_.Duplicate_Status -eq "PHYSICAL_DUPLICATE"
    } |
    Group-Object SHA256 |
    ForEach-Object {
        $_.Group |
        Select-Object -First 1
    }
)

Write-Host ("Unique physical documents: " + $uniqueRows.Count)

# ============================================================
# 3. TEXT EXTRACTION COMMAND
# ============================================================

$python = Get-Command python -ErrorAction Stop

Write-Host "[3/7] Preparing content extraction..."

$env:PYTHONPATH = Join-Path $Repo "src"

$extractor = @'
import re
import sys
from pathlib import Path

try:
    import pypdf
except Exception:
    pypdf = None

path = Path(sys.argv[1])

print("FILE=" + str(path))
print("")

text = ""

suffix = path.suffix.lower()

if suffix == ".pdf":

    if pypdf is None:
        print("EXTRACTOR_ERROR=PYPDF_NOT_AVAILABLE")
        sys.exit(0)

    try:
        reader = pypdf.PdfReader(str(path))

        parts = []

        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass

        text = "\n".join(parts)

    except Exception as exc:
        print("EXTRACTOR_ERROR=" + type(exc).__name__ + ":" + str(exc))
        sys.exit(0)

elif suffix == ".txt":

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print("EXTRACTOR_ERROR=" + type(exc).__name__ + ":" + str(exc))
        sys.exit(0)

else:

    print("EXTRACTOR_ERROR=UNSUPPORTED_EXTENSION")
    sys.exit(0)

clean = re.sub(r"\s+", " ", text)

print("TEXT_LENGTH=" + str(len(clean)))

# ------------------------------------------------------------
# TICKER
# ------------------------------------------------------------

tickers = []

for ticker in ["CVBI11", "PCIP11"]:

    if re.search(r"\b" + ticker + r"\b", clean, re.IGNORECASE):
        tickers.append(ticker)

print("TICKERS=" + ",".join(tickers))

# ------------------------------------------------------------
# FUND NAME SIGNALS
# ------------------------------------------------------------

fund_signal = False

fund_patterns = [
    r"Patria",
    r"Patr[ií]a",
    r"Cr[eé]dito",
    r"Indice de Pre[cç]os",
    r"Índice de Preços",
    r"VBI"
]

for pattern in fund_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        fund_signal = True
        break

print("FUND_SIGNAL=" + str(fund_signal))

# ------------------------------------------------------------
# MONTH
# ------------------------------------------------------------

months = [
    ("janeiro", "01"),
    ("fevereiro", "02"),
    ("marco", "03"),
    ("março", "03"),
    ("abril", "04"),
    ("maio", "05"),
    ("junho", "06"),
    ("julho", "07"),
    ("agosto", "08"),
    ("setembro", "09"),
    ("outubro", "10"),
    ("novembro", "11"),
    ("dezembro", "12")
]

periods = []

for name, number in months:

    pattern = name + r".{0,20}?(\d{4})"

    for match in re.finditer(pattern, clean, re.IGNORECASE):

        year = match.group(1)
        periods.append(year + "-" + number)

if periods:
    print("MONTH_PERIODS=" + "|".join(sorted(set(periods))))
else:
    print("MONTH_PERIODS=")

# ------------------------------------------------------------
# QUARTER
# ------------------------------------------------------------

quarters = []

patterns = [
    r"\b([1-4])T\s*([0-9]{2})\b",
    r"\b([1-4])T\s*([0-9]{4})\b"
]

for pattern in patterns:

    for match in re.finditer(pattern, clean, re.IGNORECASE):

        q = match.group(1)
        y = match.group(2)

        if len(y) == 2:
            y = "20" + y

        quarters.append(y + "-T" + q)

if quarters:
    print("QUARTER_PERIODS=" + "|".join(sorted(set(quarters))))
else:
    print("QUARTER_PERIODS=")

# ------------------------------------------------------------
# REFERENCE DATE
# ------------------------------------------------------------

date_patterns = [
    r"\b([0-3][0-9])[/-]([0-1][0-9])[/-](20[0-9]{2})\b",
    r"\b(20[0-9]{2})[-/]([0-1][0-9])[-/]([0-3][0-9])\b"
]

dates = []

for pattern in date_patterns:

    for match in re.finditer(pattern, clean):

        if pattern.startswith(r"\b([0-3]"):

            dates.append(
                match.group(3) + "-" +
                match.group(2) + "-" +
                match.group(1)
            )

        else:

            dates.append(
                match.group(1) + "-" +
                match.group(2) + "-" +
                match.group(3)
            )

if dates:
    print("DATES=" + "|".join(sorted(set(dates))[:20]))
else:
    print("DATES=")

# ------------------------------------------------------------
# DISTRIBUTION SIGNAL
# ------------------------------------------------------------

distribution = False

distribution_patterns = [
    r"distribui",
    r"rendimentos",
    r"amortiza",
    r"rendimento por cota"
]

for pattern in distribution_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        distribution = True
        break

print("DISTRIBUTION_SIGNAL=" + str(distribution))

# ------------------------------------------------------------
# NAV / PL SIGNAL
# ------------------------------------------------------------

nav_signal = False

nav_patterns = [
    r"valor patrimonial",
    r"patrim[oô]nio l[ií]quido",
    r"valor da cota",
    r"cota patrimonial",
    r"valor patrimonial da cota"
]

for pattern in nav_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        nav_signal = True
        break

print("NAV_SIGNAL=" + str(nav_signal))

# ------------------------------------------------------------
# PORTFOLIO SIGNAL
# ------------------------------------------------------------

portfolio = False

portfolio_patterns = [
    r"CRI",
    r"Certificados de Receb[ií]veis Imobili[aá]rios",
    r"carteira",
    r"opera[cç][oõ]es estruturadas",
    r"ativos"
]

for pattern in portfolio_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        portfolio = True
        break

print("PORTFOLIO_SIGNAL=" + str(portfolio))

# ------------------------------------------------------------
# RESULT SIGNAL
# ------------------------------------------------------------

result_signal = False

result_patterns = [
    r"resultado distribu[ií]vel",
    r"resultado financeiro",
    r"resultado do fundo",
    r"receitas",
    r"despesas"
]

for pattern in result_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        result_signal = True
        break

print("RESULT_SIGNAL=" + str(result_signal))

# ------------------------------------------------------------
# EVENT SIGNAL
# ------------------------------------------------------------

event_signal = False

event_patterns = [
    r"fato relevante",
    r"assembleia",
    r"emiss[aã]o de cotas",
    r"altera[cç][aã]o do nome",
    r"reorganiza[cç][aã]o"
]

for pattern in event_patterns:

    if re.search(pattern, clean, re.IGNORECASE):
        event_signal = True
        break

print("EVENT_SIGNAL=" + str(event_signal))
'@

$TempPy = Join-Path $env:TEMP "pcip11_content_triage_0695_2r2.py"

Set-Content `
    -Path $TempPy `
    -Value $extractor `
    -Encoding UTF8

# ============================================================
# 4. PROCESS DOCUMENTS
# ============================================================

Write-Host "[4/7] Extracting document content..."

$resultRows = New-Object System.Collections.Generic.List[object]

$counter = 0

foreach ($row in $uniqueRows) {

    $counter++

    $filePath = Join-Path $Repo $row.RelativePath

    Write-Progress `
        -Activity "PCIP11 Content Triage" `
        -Status $row.Original_FileName `
        -PercentComplete (($counter / $uniqueRows.Count) * 100)

    if (-not (Test-Path $filePath)) {

        $resultRows.Add(
            [pscustomobject]@{
                Historical_ID = $row.Historical_ID
                SHA256 = $row.SHA256
                FileName = $row.Original_FileName
                RelativePath = $row.RelativePath
                Historical_Ticker = $row.Historical_Ticker
                Storage_Year = $row.Storage_Year
                Document_Year = $row.Document_Year
                Document_Period = $row.Document_Period
                Canonical_Type = $row.Canonical_Type
                Extraction_Status = "FILE_NOT_FOUND"
                Content_Ticker = ""
                Fund_Signal = ""
                Month_Periods = ""
                Quarter_Periods = ""
                Dates = ""
                Distribution_Signal = ""
                NAV_Signal = ""
                Portfolio_Signal = ""
                Result_Signal = ""
                Event_Signal = ""
            }
        )

        continue
    }

    try {

        $output = & python $TempPy $filePath 2>&1

        $outputText = ($output | Out-String)

        $contentTicker = ""
        $fundSignal = ""
        $monthPeriods = ""
        $quarterPeriods = ""
        $dates = ""
        $distributionSignal = ""
        $navSignal = ""
        $portfolioSignal = ""
        $resultSignal = ""
        $eventSignal = ""

        if ($outputText -match "(?m)^TICKERS=(.*)$") {
            $contentTicker = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^FUND_SIGNAL=(.*)$") {
            $fundSignal = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^MONTH_PERIODS=(.*)$") {
            $monthPeriods = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^QUARTER_PERIODS=(.*)$") {
            $quarterPeriods = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^DATES=(.*)$") {
            $dates = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^DISTRIBUTION_SIGNAL=(.*)$") {
            $distributionSignal = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^NAV_SIGNAL=(.*)$") {
            $navSignal = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^PORTFOLIO_SIGNAL=(.*)$") {
            $portfolioSignal = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^RESULT_SIGNAL=(.*)$") {
            $resultSignal = $Matches[1].Trim()
        }

        if ($outputText -match "(?m)^EVENT_SIGNAL=(.*)$") {
            $eventSignal = $Matches[1].Trim()
        }

        $status = "EXTRACTED"

        if ($outputText -match "EXTRACTOR_ERROR=") {
            $status = "EXTRACTOR_ERROR"
        }

        $resultRows.Add(
            [pscustomobject]@{
                Historical_ID = $row.Historical_ID
                SHA256 = $row.SHA256
                FileName = $row.Original_FileName
                RelativePath = $row.RelativePath
                Historical_Ticker = $row.Historical_Ticker
                Storage_Year = $row.Storage_Year
                Document_Year = $row.Document_Year
                Document_Period = $row.Document_Period
                Canonical_Type = $row.Canonical_Type
                Extraction_Status = $status
                Content_Ticker = $contentTicker
                Fund_Signal = $fundSignal
                Month_Periods = $monthPeriods
                Quarter_Periods = $quarterPeriods
                Dates = $dates
                Distribution_Signal = $distributionSignal
                NAV_Signal = $navSignal
                Portfolio_Signal = $portfolioSignal
                Result_Signal = $resultSignal
                Event_Signal = $eventSignal
            }
        )
    }
    catch {

        $resultRows.Add(
            [pscustomobject]@{
                Historical_ID = $row.Historical_ID
                SHA256 = $row.SHA256
                FileName = $row.Original_FileName
                RelativePath = $row.RelativePath
                Historical_Ticker = $row.Historical_Ticker
                Storage_Year = $row.Storage_Year
                Document_Year = $row.Document_Year
                Document_Period = $row.Document_Period
                Canonical_Type = $row.Canonical_Type
                Extraction_Status = "EXCEPTION"
                Content_Ticker = ""
                Fund_Signal = ""
                Month_Periods = ""
                Quarter_Periods = ""
                Dates = ""
                Distribution_Signal = ""
                NAV_Signal = ""
                Portfolio_Signal = ""
                Result_Signal = ""
                Event_Signal = ""
            }
        )
    }
}

Write-Progress `
    -Activity "PCIP11 Content Triage" `
    -Completed

# ============================================================
# 5. SAVE CSV
# ============================================================

Write-Host "[5/7] Writing triage CSV..."

$resultRows |
    Sort-Object Document_Year, Document_Period, Canonical_Type, FileName |
    Export-Csv `
        -Path $OutputCsv `
        -NoTypeInformation `
        -Encoding UTF8

# ============================================================
# 6. STATISTICS
# ============================================================

Write-Host "[6/7] Building triage report..."

$totalDocs = $resultRows.Count

$extracted = @(
    $resultRows |
    Where-Object {
        $_.Extraction_Status -eq "EXTRACTED"
    }
).Count

$extractErrors = @(
    $resultRows |
    Where-Object {
        $_.Extraction_Status -ne "EXTRACTED"
    }
).Count

$contentCVBI = @(
    $resultRows |
    Where-Object {
        $_.Content_Ticker -match "CVBI11"
    }
).Count

$contentPCIP = @(
    $resultRows |
    Where-Object {
        $_.Content_Ticker -match "PCIP11"
    }
).Count

$distributionDocs = @(
    $resultRows |
    Where-Object {
        $_.Distribution_Signal -eq "True"
    }
).Count

$navDocs = @(
    $resultRows |
    Where-Object {
        $_.NAV_Signal -eq "True"
    }
).Count

$portfolioDocs = @(
    $resultRows |
    Where-Object {
        $_.Portfolio_Signal -eq "True"
    }
).Count

$resultDocs = @(
    $resultRows |
    Where-Object {
        $_.Result_Signal -eq "True"
    }
).Count

$eventDocs = @(
    $resultRows |
    Where-Object {
        $_.Event_Signal -eq "True"
    }
).Count

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("# 0695.2R2 - PCIP11 Content Triage")
$lines.Add("")
$lines.Add("Status: CONTENT TRIAGE COMPLETED")
$lines.Add("Period: 2024-2026")
$lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("")

$lines.Add("## Processing")
$lines.Add("")
$lines.Add("- Physical documents processed: " + $totalDocs)
$lines.Add("- Extracted: " + $extracted)
$lines.Add("- Extraction errors: " + $extractErrors)
$lines.Add("")

$lines.Add("## Content identity")
$lines.Add("")
$lines.Add("- CVBI11 found in content: " + $contentCVBI)
$lines.Add("- PCIP11 found in content: " + $contentPCIP)
$lines.Add("")

$lines.Add("## Content signals")
$lines.Add("")
$lines.Add("- Distribution documents: " + $distributionDocs)
$lines.Add("- NAV/PL documents: " + $navDocs)
$lines.Add("- Portfolio documents: " + $portfolioDocs)
$lines.Add("- Result documents: " + $resultDocs)
$lines.Add("- Event documents: " + $eventDocs)
$lines.Add("")

$lines.Add("## Rules")
$lines.Add("")
$lines.Add("- Content is evidence for triage only.")
$lines.Add("- No historical metric is promoted.")
$lines.Add("- No Vault note is modified.")
$lines.Add("- No document is deleted.")
$lines.Add("- Missing content is kept as a GAP.")
$lines.Add("")

$lines.Add("## Outputs")
$lines.Add("")
$lines.Add("- CSV: " + $OutputCsv)
$lines.Add("- Report: " + $OutputMd)
$lines.Add("")

$lines.Add("## Status")
$lines.Add("")
$lines.Add("0695.2R2 CONTENT TRIAGE COMPLETED")

$lines |
    Set-Content `
        -Path $OutputMd `
        -Encoding UTF8

# ============================================================
# 7. FINAL
# ============================================================

Remove-Item $TempPy -Force -ErrorAction SilentlyContinue

Write-Host "[7/7] Final validation..."
Write-Host ""

Write-Host ("Physical documents : " + $totalDocs)
Write-Host ("Extracted          : " + $extracted)
Write-Host ("Extraction errors  : " + $extractErrors)
Write-Host ("CVBI11 content     : " + $contentCVBI)
Write-Host ("PCIP11 content     : " + $contentPCIP)
Write-Host ("Distribution docs  : " + $distributionDocs)
Write-Host ("NAV/PL docs        : " + $navDocs)
Write-Host ("Portfolio docs     : " + $portfolioDocs)
Write-Host ("Result docs        : " + $resultDocs)
Write-Host ("Event docs         : " + $eventDocs)
Write-Host ""

Write-Host ("CSV                : " + $OutputCsv)
Write-Host ("Report             : " + $OutputMd)
Write-Host ""
Write-Host "STATUS: 0695.2R2 CONTENT TRIAGE COMPLETED"
Write-Host "============================================================"