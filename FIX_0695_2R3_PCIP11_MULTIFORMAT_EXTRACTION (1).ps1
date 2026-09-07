$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"

$Manifest = Join-Path $Repo "reports\PCIP11_EXTRACTION_MANIFEST_0695_2.csv"
$OutDir = Join-Path $Repo "reports"

$OutputCsv = Join-Path $OutDir "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3.csv"
$OutputMd = Join-Path $OutDir "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.2R3 - PCIP11 MULTI-FORMAT EXTRACTION"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# 1. VALIDATE INPUT
# ============================================================

Write-Host "[1/8] Validating manifest..."

if (-not (Test-Path $Manifest)) {
    throw "Manifest not found: $Manifest"
}

$manifestRows = Import-Csv $Manifest

Write-Host ("Manifest rows: " + $manifestRows.Count)

# ============================================================
# 2. UNIQUE PHYSICAL DOCUMENTS
# ============================================================

Write-Host "[2/8] Selecting unique physical documents..."

$uniqueRows = @(
    $manifestRows |
    Where-Object {
        $_.SHA256 -and
        $_.SHA256 -ne "HASH_ERROR"
    } |
    Group-Object SHA256 |
    ForEach-Object {
        $_.Group | Select-Object -First 1
    }
)

# Add HASH_ERROR records separately, if any
$hashErrorRows = @(
    $manifestRows |
    Where-Object {
        -not $_.SHA256 -or
        $_.SHA256 -eq "HASH_ERROR"
    }
)

$uniqueRows = @(
    $uniqueRows + $hashErrorRows
)

Write-Host ("Unique physical documents: " + $uniqueRows.Count)

# ============================================================
# 3. PYTHON MULTI-FORMAT EXTRACTOR
# ============================================================

Write-Host "[3/8] Preparing multi-format extractor..."

$env:PYTHONPATH = Join-Path $Repo "src"

$python = Get-Command python -ErrorAction Stop

$ExtractorCode = @'
import sys
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
try:
    import pypdf
except Exception:
    pypdf = None
try:
    import openpyxl
except Exception:
    openpyxl = None
CNPJ = "28729197000113"
MONTHS = {
    "janeiro": "01",
    "fevereiro": "02",
    "marco": "03",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}
def clean_text(value):
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
def extract_pdf(path):
    if pypdf is None:
        raise RuntimeError("PYPDF_NOT_AVAILABLE")
    reader = pypdf.PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(parts)
def extract_xml_bytes(data):
    try:
        root = ET.fromstring(data)
        parts = []
        for element in root.iter():
            if element.text:
                value = clean_text(element.text)
                if value:
                    parts.append(value)
            for key, value in element.attrib.items():
                value = clean_text(value)
                if value:
                    parts.append(value)
        return "\n".join(parts)
    except Exception:
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
def extract_xml(path):
    data = path.read_bytes()
    return extract_xml_bytes(data)
def extract_zip(path):
    parts = []
    with zipfile.ZipFile(path, "r") as archive:
        members = archive.namelist()
        print("ZIP_MEMBERS=" + "|".join(members[:100]))
        for member in members:
            lower = member.lower()
            if lower.endswith(".xml"):
                try:
                    data = archive.read(member)
                    text = extract_xml_bytes(data)
                    if text:
                        parts.append(text)
                except Exception:
                    pass
            elif lower.endswith(".txt"):
                try:
                    data = archive.read(member)
                    parts.append(
                        data.decode("utf-8", errors="replace")
                    )
                except Exception:
                    pass
    return "\n".join(parts)
def extract_xlsx(path):
    if openpyxl is None:
        raise RuntimeError("OPENPYXL_NOT_AVAILABLE")
    workbook = openpyxl.load_workbook(
        filename=str(path),
        read_only=True,
        data_only=True
    )
    print("XLSX_SHEETS=" + "|".join(workbook.sheetnames))
    parts = []
    for worksheet in workbook.worksheets:
        parts.append("SHEET=" + worksheet.title)
        max_rows = 1000
        row_count = 0
        for row in worksheet.iter_rows(values_only=True):
            row_count += 1
            if row_count > max_rows:
                break
            values = []
            for cell in row:
                if cell is None:
                    values.append("")
                else:
                    values.append(clean_text(cell))
            line = " | ".join(values).strip()
            if line:
                parts.append(line)
    workbook.close()
    return "\n".join(parts)
def detect_ticker(text):
    tickers = []
    if re.search(r"\bCVBI11\b", text, re.IGNORECASE):
        tickers.append("CVBI11")
    if re.search(r"\bPCIP11\b", text, re.IGNORECASE):
        tickers.append("PCIP11")
    # Same CNPJ is strong identity evidence
    if re.search(r"28[.\s-]?729[.\s-]?197[/. -]?0001[/-]?13", text):
        if "PCIP11" not in tickers:
            tickers.append("PCIP11")
    return tickers
def detect_dates(text):
    dates = []
    patterns = [
        r"\b([0-3][0-9])[/.-]([0-1][0-9])[/.-](20[0-9]{2})\b",
        r"\b(20[0-9]{2})[-.]([0-1][0-9])[-.]([0-3][0-9])\b"
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if pattern.startswith(r"\b([0-3]"):
                value = (
                    match.group(3)
                    + "-"
                    + match.group(2)
                    + "-"
                    + match.group(1)
                )
            else:
                value = (
                    match.group(1)
                    + "-"
                    + match.group(2)
                    + "-"
                    + match.group(3)
                )
            dates.append(value)
    return sorted(set(dates))
def detect_month_periods(text):
    periods = []
    for month, number in MONTHS.items():
        pattern = month + r".{0,30}?((?:19|20)\d{2})"
        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):
            periods.append(
                match.group(1) + "-" + number
            )
    return sorted(set(periods))
def detect_quarters(text):
    periods = []
    patterns = [
        r"\b([1-4])T\s*((?:19|20)\d{2})\b",
        r"\b([1-4])T\s*(\d{2})\b"
    ]
    for pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):
            quarter = match.group(1)
            year = match.group(2)
            if len(year) == 2:
                year = "20" + year
            periods.append(
                year + "-T" + quarter
            )
    return sorted(set(periods))
def detect_encoded_document_date(filename):
    # REL21052026V01
    # ACE08072026V01
    # FRV27082026V01
    matches = re.findall(
        r"(?:REL|ACE|FRV)(\d{8})V\d+",
        filename.upper()
    )
    dates = []
    for value in matches:
        day = value[0:2]
        month = value[2:4]
        year = value[4:8]
        if (
            1900 <= int(year) <= 2100 and
            1 <= int(month) <= 12 and
            1 <= int(day) <= 31
        ):
            dates.append(
                year + "-" + month + "-" + day
            )
    return sorted(set(dates))
def detect_document_period(filename, text):
    periods = []
    encoded_dates = detect_encoded_document_date(filename)
    for date in encoded_dates:
        periods.append(
            "DATE:" + date
        )
    month_periods = detect_month_periods(filename + " " + text)
    for period in month_periods:
        periods.append(
            "MONTH:" + period
        )
    quarter_periods = detect_quarters(
        filename + " " + text
    )
    for period in quarter_periods:
        periods.append(
            "QUARTER:" + period
        )
    return sorted(set(periods))
def detect_signals(text):
    lower = text.lower()
    distribution_terms = [
        "distribui",
        "rendimentos",
        "amortiza",
        "rendimento por cota"
    ]
    nav_terms = [
        "valor patrimonial",
        "patrimônio líquido",
        "patrimonio liquido",
        "valor da cota",
        "cota patrimonial"
    ]
    portfolio_terms = [
        "cri",
        "certificados de recebíveis imobiliários",
        "certificados de recebiveis imobiliarios",
        "carteira",
        "ativos"
    ]
    result_terms = [
        "resultado distribuível",
        "resultado distribuivel",
        "resultado financeiro",
        "resultado do fundo",
        "receitas",
        "despesas"
    ]
    event_terms = [
        "fato relevante",
        "assembleia",
        "emissão de cotas",
        "emissao de cotas",
        "alteração do nome",
        "alteracao do nome",
        "reorganização societária",
        "reorganizacao societaria"
    ]
    def has_term(terms):
        return any(term in lower for term in terms)
    return {
        "Distribution": has_term(distribution_terms),
        "NAV": has_term(nav_terms),
        "Portfolio": has_term(portfolio_terms),
        "Result": has_term(result_terms),
        "Event": has_term(event_terms),
    }
def main():
    path = Path(sys.argv[1])
    suffix = path.suffix.lower()
    print("FILE=" + str(path))
    print("EXTENSION=" + suffix)
    try:
        if suffix == ".pdf":
            text = extract_pdf(path)
        elif suffix == ".xml":
            text = extract_xml(path)
        elif suffix == ".zip":
            text = extract_zip(path)
        elif suffix in [".xlsx", ".xlsm", ".xltx", ".xltm"]:
            text = extract_xlsx(path)
        elif suffix in [".txt", ".csv"]:
            text = path.read_text(
                encoding="utf-8",
                errors="replace"
            )
        else:
            print("STATUS=UNSUPPORTED_EXTENSION")
            sys.exit(0)
        text = clean_text(text)
        print("STATUS=EXTRACTED")
        print("TEXT_LENGTH=" + str(len(text)))
        tickers = detect_ticker(text)
        print(
            "CONTENT_TICKER="
            + ",".join(tickers)
        )
        print(
            "CNPJ_SIGNAL="
            + str(CNPJ in re.sub(r"\D", "", text))
        )
        periods = detect_document_period(
            path.name,
            text
        )
        print(
            "CONTENT_PERIODS="
            + "|".join(periods)
        )
        dates = detect_dates(text)
        print(
            "CONTENT_DATES="
            + "|".join(dates[:50])
        )
        quarters = detect_quarters(text)
        print(
            "CONTENT_QUARTERS="
            + "|".join(quarters)
        )
        months = detect_month_periods(text)
        print(
            "CONTENT_MONTHS="
            + "|".join(months)
        )
        signals = detect_signals(text)
        print(
            "DISTRIBUTION_SIGNAL="
            + str(signals["Distribution"])
        )
        print(
            "NAV_SIGNAL="
            + str(signals["NAV"])
        )
        print(
            "PORTFOLIO_SIGNAL="
            + str(signals["Portfolio"])
        )
        print(
            "RESULT_SIGNAL="
            + str(signals["Result"])
        )
        print(
            "EVENT_SIGNAL="
            + str(signals["Event"])
        )
    except Exception as exc:
        print("STATUS=EXTRACTOR_ERROR")
        print(
            "ERROR_TYPE="
            + type(exc).__name__
        )
        print(
            "ERROR_MESSAGE="
            + str(exc).replace("\n", " ")
        )
if __name__ == "__main__":
    main()
'@

$TempPy = Join-Path $env:TEMP "pcip11_multiformat_0695_2r3.py"

Set-Content `
    -Path $TempPy `
    -Value $ExtractorCode `
    -Encoding UTF8

# ============================================================
# 4. PROCESS
# ============================================================

Write-Host "[4/8] Extracting content from unique physical documents..."

$resultRows = New-Object System.Collections.Generic.List[object]

$counter = 0

foreach ($row in $uniqueRows) {
    $counter++
    $filePath = Join-Path $Repo $row.RelativePath
    $displayName = [string]$row.Original_FileName
    if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = [string]$row.FileName }
    if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = [System.IO.Path]::GetFileName($filePath) }
    if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = "Document_" + $counter }
    $percent = if ($uniqueRows.Count -gt 0) { [math]::Min(100,[math]::Round(($counter/$uniqueRows.Count)*100,1)) } else { 100 }
    Write-Progress `
        -Activity "PCIP11 Multi-format extraction" `
        -Status $displayName `
        -PercentComplete $percent
    $extension = [System.IO.Path]::GetExtension(
        $filePath
    ).ToLower()
    $status = ""
    $contentTicker = ""
    $cnpjSignal = ""
    $periods = ""
    $dates = ""
    $quarters = ""
    $months = ""
    $distributionSignal = ""
    $navSignal = ""
    $portfolioSignal = ""
    $resultSignal = ""
    $eventSignal = ""
    $errorType = ""
    $errorMessage = ""
    $textLength = 0
    if (-not (Test-Path $filePath)) {
        $status = "FILE_NOT_FOUND"
    }
    else {
        try {
            $output = & python $TempPy $filePath 2>&1
            $outputText = (
                $output |
                Out-String
            )
            if ($outputText -match "(?m)^STATUS=(.*)$") {
                $status = $Matches[1].Trim()
            }
            else {
                $status = "NO_STATUS"
            }
            if ($outputText -match "(?m)^TEXT_LENGTH=(.*)$") {
                $textLength = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CONTENT_TICKER=(.*)$") {
                $contentTicker = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CNPJ_SIGNAL=(.*)$") {
                $cnpjSignal = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CONTENT_PERIODS=(.*)$") {
                $periods = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CONTENT_DATES=(.*)$") {
                $dates = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CONTENT_QUARTERS=(.*)$") {
                $quarters = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^CONTENT_MONTHS=(.*)$") {
                $months = $Matches[1].Trim()
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
            if ($outputText -match "(?m)^ERROR_TYPE=(.*)$") {
                $errorType = $Matches[1].Trim()
            }
            if ($outputText -match "(?m)^ERROR_MESSAGE=(.*)$") {
                $errorMessage = $Matches[1].Trim()
            }
        }
        catch {
            $status = "POWERSHELL_EXCEPTION"
            $errorType = $_.Exception.GetType().Name
            $errorMessage = $_.Exception.Message
        }
    }
    $resultRows.Add(
        [pscustomobject]@{
            Historical_ID = $row.Historical_ID
            SHA256 = $row.SHA256
            FileName = $displayName
            RelativePath = $row.RelativePath
            Extension = $extension
            Original_Ticker = $row.Historical_Ticker
            Content_Ticker = $contentTicker
            CNPJ_Signal = $cnpjSignal
            Storage_Year = $row.Storage_Year
            Document_Year = $row.Document_Year
            Document_Period_Manifest = $row.Document_Period
            Content_Periods = $periods
            Content_Dates = $dates
            Content_Quarters = $quarters
            Content_Months = $months
            Canonical_Type = $row.Canonical_Type
            Priority = $row.Priority
            Extraction_Status = $status
            Text_Length = $textLength
            Distribution_Signal = $distributionSignal
            NAV_Signal = $navSignal
            Portfolio_Signal = $portfolioSignal
            Result_Signal = $resultSignal
            Event_Signal = $eventSignal
            Error_Type = $errorType
            Error_Message = $errorMessage
        }
    )
}

Write-Progress `
    -Activity "PCIP11 Multi-format extraction" `
    -Completed

# ============================================================
# 5. SAVE CSV
# ============================================================

Write-Host "[5/8] Saving extraction results..."

$resultRows |
    Sort-Object `
        Storage_Year,
        Canonical_Type,
        FileName |
    Export-Csv `
        -Path $OutputCsv `
        -NoTypeInformation `
        -Encoding UTF8

# ============================================================
# 6. STATISTICS
# ============================================================

Write-Host "[6/8] Building statistics..."

$total = $resultRows.Count

$extracted = @(
    $resultRows |
    Where-Object {
        $_.Extraction_Status -eq "EXTRACTED"
    }
).Count

$errors = @(
    $resultRows |
    Where-Object {
        $_.Extraction_Status -ne "EXTRACTED"
    }
).Count

$pdfCount = @(
    $resultRows |
    Where-Object {
        $_.Extension -eq ".pdf"
    }
).Count

$xmlCount = @(
    $resultRows |
    Where-Object {
        $_.Extension -eq ".xml"
    }
).Count

$zipCount = @(
    $resultRows |
    Where-Object {
        $_.Extension -eq ".zip"
    }
).Count

$xlsxCount = @(
    $resultRows |
    Where-Object {
        $_.Extension -in @(
            ".xlsx",
            ".xlsm",
            ".xltx",
            ".xltm"
        )
    }
).Count

$cvbiContent = @(
    $resultRows |
    Where-Object {
        $_.Content_Ticker -match "CVBI11"
    }
).Count

$pcipContent = @(
    $resultRows |
    Where-Object {
        $_.Content_Ticker -match "PCIP11"
    }
).Count

$cnpjContent = @(
    $resultRows |
    Where-Object {
        $_.CNPJ_Signal -eq "True"
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

$statusGroups = $resultRows |
    Group-Object Extraction_Status |
    Sort-Object Name

$typeGroups = $resultRows |
    Group-Object Extension |
    Sort-Object Name

# ============================================================
# 7. REPORT
# ============================================================

Write-Host "[7/8] Writing report..."

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("# 0695.2R3 - PCIP11 Multi-format Content Extraction")
$lines.Add("")
$lines.Add("Status: MULTI-FORMAT TRIAGE COMPLETED")
$lines.Add("Period: 2024-2026")
$lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("")

$lines.Add("## Processing")
$lines.Add("")
$lines.Add("- Unique physical documents: " + $total)
$lines.Add("- Extracted: " + $extracted)
$lines.Add("- Errors: " + $errors)
$lines.Add("")

$lines.Add("## Formats")
$lines.Add("")
$lines.Add("- PDF: " + $pdfCount)
$lines.Add("- XML: " + $xmlCount)
$lines.Add("- ZIP: " + $zipCount)
$lines.Add("- XLSX/XLSM/XLTX/XLTM: " + $xlsxCount)
$lines.Add("")

$lines.Add("## Identity")
$lines.Add("")
$lines.Add("- CVBI11 found in content: " + $cvbiContent)
$lines.Add("- PCIP11 found in content: " + $pcipContent)
$lines.Add("- CNPJ found in content: " + $cnpjContent)
$lines.Add("")

$lines.Add("## Signals")
$lines.Add("")
$lines.Add("- Distribution: " + $distributionDocs)
$lines.Add("- NAV/PL: " + $navDocs)
$lines.Add("- Portfolio: " + $portfolioDocs)
$lines.Add("- Result: " + $resultDocs)
$lines.Add("- Events: " + $eventDocs)
$lines.Add("")

$lines.Add("## Extraction statuses")
$lines.Add("")

foreach ($g in $statusGroups) {
    $lines.Add("- " + $g.Name + ": " + $g.Count)
}

$lines.Add("")
$lines.Add("## Extensions")
$lines.Add("")

foreach ($g in $typeGroups) {
    $label = $g.Name
    if ([string]::IsNullOrWhiteSpace($label)) {
        $label = "NO_EXTENSION"
    }
    $lines.Add("- " + $label + ": " + $g.Count)
}

$lines.Add("")
$lines.Add("## Identity policy")
$lines.Add("")
$lines.Add("- SHA256 identifies the physical document.")
$lines.Add("- CNPJ is used as strong fund identity evidence.")
$lines.Add("- CVBI11 and PCIP11 are preserved as historical/current ticker evidence.")
$lines.Add("- UUIDs and document identifiers are never treated as years.")
$lines.Add("- Content-derived periods are kept separate from manifest periods.")
$lines.Add("- Errors remain GAPs.")
$lines.Add("")

$lines.Add("## Safety")
$lines.Add("")
$lines.Add("- No Vault note modified.")
$lines.Add("- No asset note modified.")
$lines.Add("- No metric promoted.")
$lines.Add("- No source document modified.")
$lines.Add("")

$lines.Add("## Outputs")
$lines.Add("")
$lines.Add("- CSV: " + $OutputCsv)
$lines.Add("- Report: " + $OutputMd)
$lines.Add("")

$lines.Add("## Status")
$lines.Add("")
$lines.Add("0695.2R3 MULTI-FORMAT EXTRACTION COMPLETED")

$lines |
    Set-Content `
        -Path $OutputMd `
        -Encoding UTF8

# ============================================================
# 8. FINAL
# ============================================================

Remove-Item $TempPy -Force -ErrorAction SilentlyContinue

Write-Host "[8/8] Final validation..."
Write-Host ""

Write-Host ("Unique physical : " + $total)
Write-Host ("Extracted        : " + $extracted)
Write-Host ("Errors           : " + $errors)
Write-Host ("PDF              : " + $pdfCount)
Write-Host ("XML              : " + $xmlCount)
Write-Host ("ZIP              : " + $zipCount)
Write-Host ("XLSX             : " + $xlsxCount)
Write-Host ("CVBI11 content   : " + $cvbiContent)
Write-Host ("PCIP11 content   : " + $pcipContent)
Write-Host ("CNPJ content     : " + $cnpjContent)
Write-Host ("Distribution     : " + $distributionDocs)
Write-Host ("NAV/PL           : " + $navDocs)
Write-Host ("Portfolio        : " + $portfolioDocs)
Write-Host ("Result           : " + $resultDocs)
Write-Host ("Events           : " + $eventDocs)
Write-Host ""

Write-Host ("CSV              : " + $OutputCsv)
Write-Host ("Report           : " + $OutputMd)
Write-Host ""
Write-Host "STATUS: 0695.2R3 MULTI-FORMAT EXTRACTION COMPLETED"
Write-Host "============================================================"
Get-Content ".\reports\PCIP11_MULTIFORMAT_TRIAGE_0695_2R3.md" -Encoding UTF8
