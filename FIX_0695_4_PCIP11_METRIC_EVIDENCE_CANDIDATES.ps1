$ErrorActionPreference = 'Stop'

$Repo = 'D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1'
$ClassCsv = Join-Path $Repo 'reports\PCIP11_CONTENT_CLASSIFICATION_0695_3.csv'
$OutDir = Join-Path $Repo 'reports'
$OutCsv = Join-Path $OutDir 'PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv'
$OutMd = Join-Path $OutDir 'PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.md'
$TempPy = Join-Path $env:TEMP 'pcip11_metric_evidence_0695_4.py'

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ''
Write-Host '============================================================'
Write-Host '0695.4 - PCIP11 METRIC EVIDENCE CANDIDATES'
Write-Host '============================================================'
Write-Host ''

Write-Host '[1/7] Validating classification input...'
if (-not (Test-Path -LiteralPath $ClassCsv)) { throw "Classification CSV not found: $ClassCsv" }
$rows = @(Import-Csv -LiteralPath $ClassCsv)
if ($rows.Count -eq 0) { throw 'Classification CSV is empty.' }
Write-Host ('Input rows: ' + $rows.Count)

Write-Host '[2/7] Preparing isolated evidence extractor...'
$pythonExe = (Get-Command python -ErrorAction Stop).Source

$py = @'
import sys, re, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
try:
    import pypdf
except Exception:
    pypdf=None
try:
    import openpyxl
except Exception:
    openpyxl=None

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def xml_text(data):
    try:
        root=ET.fromstring(data)
        parts=[]
        for e in root.iter():
            if e.text: parts.append(clean(e.text))
            for v in e.attrib.values(): parts.append(clean(v))
        return ' '.join(x for x in parts if x)
    except Exception:
        return data.decode('utf-8', errors='replace')

def extract(path):
    suf=path.suffix.lower()
    if suf=='.pdf':
        if pypdf is None: raise RuntimeError('PYPDF_NOT_AVAILABLE')
        r=pypdf.PdfReader(str(path))
        return '\n'.join((p.extract_text() or '') for p in r.pages)
    if suf=='.xml': return xml_text(path.read_bytes())
    if suf=='.zip':
        parts=[]
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                ln=n.lower()
                try:
                    d=z.read(n)
                    if ln.endswith('.xml'): parts.append(xml_text(d))
                    elif ln.endswith(('.txt','.csv')): parts.append(d.decode('utf-8',errors='replace'))
                except Exception: pass
        return '\n'.join(parts)
    if suf in ('.xlsx','.xlsm','.xltx','.xltm'):
        if openpyxl is None: raise RuntimeError('OPENPYXL_NOT_AVAILABLE')
        wb=openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        parts=[]
        for ws in wb.worksheets:
            parts.append('SHEET='+ws.title)
            for i,row in enumerate(ws.iter_rows(values_only=True),1):
                if i>2000: break
                parts.append(' | '.join(clean(x) for x in row))
        wb.close()
        return '\n'.join(parts)
    return path.read_text(encoding='utf-8', errors='replace')

def snippets(text, terms, width=220, limit=6):
    t=clean(text)
    low=t.lower()
    found=[]
    for term in terms:
        start=0
        terml=term.lower()
        while len(found)<limit:
            i=low.find(terml,start)
            if i<0: break
            a=max(0,i-width); b=min(len(t),i+len(term)+width)
            found.append(f'[{term}] {t[a:b]}')
            start=i+len(term)
    return found[:limit]

def main():
    path=Path(sys.argv[1])
    text=extract(path)
    text=clean(text)
    groups={
      'DISTRIBUTION':['rendimento por cota','rendimento distribu','distribuição','distribuicao','rendimentos','amortização','amortizacao'],
      'NAV_PL':['valor patrimonial','patrimônio líquido','patrimonio liquido','valor da cota','cota patrimonial'],
      'RESULT':['resultado distribuível','resultado distribuivel','resultado financeiro','resultado do fundo','receitas','despesas'],
      'PORTFOLIO_CREDIT':['IPCA','CDI','CRI','LTV','spread','carteira','lastro','garantia','devedor','rating'],
      'EVENT':['fato relevante','assembleia','emissão de cotas','emissao de cotas','ato do administrador','edital de convocação','edital de convocacao','reorganização','reorganizacao']
    }
    print('STATUS=EXTRACTED')
    print('TEXT_LENGTH='+str(len(text)))
    for g,terms in groups.items():
        print(g+'_SNIPPETS='+ ' || '.join(snippets(text,terms)))

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('STATUS=EXTRACTOR_ERROR')
        print('ERROR_TYPE='+type(e).__name__)
        print('ERROR_MESSAGE='+str(e).replace('\n',' '))
'@
Set-Content -LiteralPath $TempPy -Value $py -Encoding UTF8

Write-Host '[3/7] Selecting evidence-relevant documents...'
# Do NOT treat the 0695.3 queue as final promotion. This stage extracts evidence candidates only.
$targetRows = @(
    $rows | Where-Object {
        $_.Extraction_Status -eq 'EXTRACTED' -and
        $_.Promotion_Decision -like 'PROMOTION_CANDIDATE*'
    }
)
Write-Host ('Evidence-relevant rows: ' + $targetRows.Count)

Write-Host '[4/7] Extracting metric/evidence snippets...'
$result = New-Object System.Collections.Generic.List[object]
$i=0
foreach ($row in $targetRows) {
    $i++
    $filePath=Join-Path $Repo ([string]$row.RelativePath)
    $status=''
    $errorType=''
    $errorMessage=''
    $textLength='0'
    $dist=''
    $nav=''
    $res=''
    $port=''
    $event=''

    $displayName=[string]$row.FileName
    if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName=[System.IO.Path]::GetFileName($filePath) }
    Write-Progress -Activity '0695.4 evidence extraction' -Status $displayName -PercentComplete (($i/$targetRows.Count)*100)

    if (-not (Test-Path -LiteralPath $filePath)) {
        $status='FILE_NOT_FOUND'; $errorType='PATH_ERROR'; $errorMessage=$filePath
    } else {
        try {
            $psi=New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName=$pythonExe
            $psi.Arguments='"'+$TempPy.Replace('"','\"')+'" "'+$filePath.Replace('"','\"')+'"'
            $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true
            $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true
            $p=New-Object System.Diagnostics.Process
            $p.StartInfo=$psi; [void]$p.Start()
            $stdout=$p.StandardOutput.ReadToEnd(); $stderr=$p.StandardError.ReadToEnd(); $p.WaitForExit()
            if ($stdout -match '(?m)^STATUS=(.*)$') {$status=$Matches[1].Trim()} else {$status='NO_STATUS'}
            if ($stdout -match '(?m)^TEXT_LENGTH=(.*)$') {$textLength=$Matches[1].Trim()}
            if ($stdout -match '(?m)^DISTRIBUTION_SNIPPETS=(.*)$') {$dist=$Matches[1].Trim()}
            if ($stdout -match '(?m)^NAV_PL_SNIPPETS=(.*)$') {$nav=$Matches[1].Trim()}
            if ($stdout -match '(?m)^RESULT_SNIPPETS=(.*)$') {$res=$Matches[1].Trim()}
            if ($stdout -match '(?m)^PORTFOLIO_CREDIT_SNIPPETS=(.*)$') {$port=$Matches[1].Trim()}
            if ($stdout -match '(?m)^EVENT_SNIPPETS=(.*)$') {$event=$Matches[1].Trim()}
            if ($stdout -match '(?m)^ERROR_TYPE=(.*)$') {$errorType=$Matches[1].Trim()}
            if ($stdout -match '(?m)^ERROR_MESSAGE=(.*)$') {$errorMessage=$Matches[1].Trim()}
            if ($p.ExitCode -ne 0 -and $status -eq 'EXTRACTED') {$status='PYTHON_EXIT_NONZERO'}
            if ($status -eq 'EXTRACTOR_ERROR' -and [string]::IsNullOrWhiteSpace($errorMessage) -and $stderr) {$errorMessage=($stderr -replace '\s+',' ').Trim()}
            $p.Dispose()
        } catch { $status='POWERSHELL_EXCEPTION'; $errorType=$_.Exception.GetType().Name; $errorMessage=$_.Exception.Message }
    }

    $result.Add([pscustomobject]@{
        Historical_ID=[string]$row.Historical_ID; SHA256=[string]$row.SHA256; FileName=$displayName; RelativePath=[string]$row.RelativePath
        Extension=[string]$row.Extension; Original_Ticker=[string]$row.Original_Ticker; Content_Ticker=[string]$row.Content_Ticker; CNPJ_Signal=[string]$row.CNPJ_Signal
        Storage_Year=[string]$row.Storage_Year; Document_Year=[string]$row.Document_Year; Content_Periods=[string]$row.Content_Periods
        Canonical_Type=[string]$row.Canonical_Type; Priority=[string]$row.Priority; Identity_Class=[string]$row.Identity_Class
        Document_Role=[string]$row.Document_Role; Period_Quality=[string]$row.Period_Quality; Confidence=[string]$row.Confidence
        Promotion_Decision=[string]$row.Promotion_Decision; Extraction_Status=$status; Text_Length=$textLength
        Distribution_Evidence=$dist; NAV_PL_Evidence=$nav; Result_Evidence=$res; Portfolio_Credit_Evidence=$port; Event_Evidence=$event
        Error_Type=$errorType; Error_Message=$errorMessage
    })
}
Write-Progress -Activity '0695.4 evidence extraction' -Completed

Write-Host '[5/7] Saving evidence candidate matrix...'
$result | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8

Write-Host '[6/7] Writing report...'
$total=$result.Count
$extracted=@($result|Where-Object {$_.Extraction_Status -eq 'EXTRACTED'}).Count
$errors=$total-$extracted
$withDistribution=@($result|Where-Object {-not [string]::IsNullOrWhiteSpace($_.Distribution_Evidence)}).Count
$withNav=@($result|Where-Object {-not [string]::IsNullOrWhiteSpace($_.NAV_PL_Evidence)}).Count
$withResult=@($result|Where-Object {-not [string]::IsNullOrWhiteSpace($_.Result_Evidence)}).Count
$withPortfolio=@($result|Where-Object {-not [string]::IsNullOrWhiteSpace($_.Portfolio_Credit_Evidence)}).Count
$withEvents=@($result|Where-Object {-not [string]::IsNullOrWhiteSpace($_.Event_Evidence)}).Count

$lines=New-Object System.Collections.Generic.List[string]
$lines.Add('# 0695.4 - PCIP11 Metric Evidence Candidates')
$lines.Add('')
$lines.Add('Status: EVIDENCE CANDIDATE EXTRACTION COMPLETED - NO METRIC PROMOTED')
$lines.Add('Generated: '+(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$lines.Add('')
$lines.Add('## Processing')
$lines.Add('')
$lines.Add('- Input classification rows: '+$rows.Count)
$lines.Add('- Evidence-relevant rows: '+$total)
$lines.Add('- Extracted: '+$extracted)
$lines.Add('- Errors: '+$errors)
$lines.Add('')
$lines.Add('## Evidence groups with literal snippets')
$lines.Add('')
$lines.Add('- Distribution: '+$withDistribution)
$lines.Add('- NAV/PL: '+$withNav)
$lines.Add('- Result: '+$withResult)
$lines.Add('- Portfolio/Credit: '+$withPortfolio)
$lines.Add('- Events: '+$withEvents)
$lines.Add('')
$lines.Add('## Promotion rule')
$lines.Add('')
$lines.Add('- These are evidence candidates only.')
$lines.Add('- No metric is promoted from a signal or snippet alone.')
$lines.Add('- Each promoted metric must retain source document, period, literal evidence, and extraction rationale.')
$lines.Add('- CVBI11 historical documents remain linked to the same asset history.')
$lines.Add('')
$lines.Add('## Output')
$lines.Add('')
$lines.Add('- CSV: '+$OutCsv)
$lines.Add('')
$lines.Add('STATUS: 0695.4 EVIDENCE CANDIDATE EXTRACTION COMPLETED')
$lines | Set-Content -LiteralPath $OutMd -Encoding UTF8

Write-Host '[7/7] Final validation...'
Write-Host ('Evidence rows : '+$total)
Write-Host ('Extracted     : '+$extracted)
Write-Host ('Errors        : '+$errors)
Write-Host ('Distribution  : '+$withDistribution)
Write-Host ('NAV/PL        : '+$withNav)
Write-Host ('Result        : '+$withResult)
Write-Host ('Portfolio     : '+$withPortfolio)
Write-Host ('Events        : '+$withEvents)
Write-Host ''
Write-Host ('CSV : '+$OutCsv)
Write-Host ('MD  : '+$OutMd)
Write-Host ''
Write-Host 'STATUS: 0695.4 EVIDENCE CANDIDATE EXTRACTION COMPLETED'
Write-Host '============================================================'

Remove-Item -LiteralPath $TempPy -Force -ErrorAction SilentlyContinue
