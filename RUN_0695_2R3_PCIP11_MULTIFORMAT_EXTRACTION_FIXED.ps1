$ErrorActionPreference = "Stop"
$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Manifest = Join-Path $Repo "reports\PCIP11_EXTRACTION_MANIFEST_0695_2.csv"
$OutDir = Join-Path $Repo "reports"
$OutputCsv = Join-Path $OutDir "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"
$OutputMd = Join-Path $OutDir "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.md"
$TempPy = Join-Path $env:TEMP "pcip11_multiformat_0695_2r3_fixed.py"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (-not (Test-Path -LiteralPath $Manifest)) { throw "Manifest not found: $Manifest" }
$manifestRows = @(Import-Csv -LiteralPath $Manifest)
if ($manifestRows.Count -eq 0) { throw "Manifest is empty." }
$uniqueRows = @($manifestRows | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.SHA256) -and [string]$_.SHA256 -ne "HASH_ERROR" } | Group-Object -Property SHA256 | ForEach-Object { $_.Group | Select-Object -First 1 })
$hashErrorRows = @($manifestRows | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.SHA256) -or [string]$_.SHA256 -eq "HASH_ERROR" } | Group-Object -Property RelativePath | ForEach-Object { $_.Group | Select-Object -First 1 })
$uniqueRows = @($uniqueRows + $hashErrorRows)
if ($uniqueRows.Count -eq 0) { throw "No physical documents selected." }
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$ExtractorCode = @'
import sys,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
try: import pypdf
except Exception: pypdf=None
try: import openpyxl
except Exception: openpyxl=None
CNPJ="28729197000113"
MONTHS={"janeiro":"01","fevereiro":"02","marco":"03","março":"03","abril":"04","maio":"05","junho":"06","julho":"07","agosto":"08","setembro":"09","outubro":"10","novembro":"11","dezembro":"12"}
def clean(x): return re.sub(r"\s+"," ",str(x)).strip() if x is not None else ""
def pdf(p):
    if pypdf is None: raise RuntimeError("PYPDF_NOT_AVAILABLE")
    r=pypdf.PdfReader(str(p)); return "\n".join((q.extract_text() or "") for q in r.pages)
def xmlb(b):
    try:
        r=ET.fromstring(b); a=[]
        for e in r.iter():
            if e.text: a.append(clean(e.text))
            a += [clean(v) for v in e.attrib.values() if clean(v)]
        return "\n".join(x for x in a if x)
    except Exception: return b.decode("utf-8",errors="replace")
def xml(p): return xmlb(p.read_bytes())
def zipx(p):
    a=[]
    with zipfile.ZipFile(p,"r") as z:
        for n in z.namelist():
            try:
                b=z.read(n); l=n.lower()
                if l.endswith('.xml'): a.append(xmlb(b))
                elif l.endswith('.txt') or l.endswith('.csv'): a.append(b.decode('utf-8',errors='replace'))
            except Exception: pass
    return '\n'.join(a)
def xlsx(p):
    if openpyxl is None: raise RuntimeError("OPENPYXL_NOT_AVAILABLE")
    w=openpyxl.load_workbook(str(p),read_only=True,data_only=True); a=[]
    for s in w.worksheets:
        a.append('SHEET='+s.title)
        for i,row in enumerate(s.iter_rows(values_only=True),1):
            if i>1000: break
            v=' | '.join(clean(c) for c in row).strip()
            if v: a.append(v)
    w.close(); return '\n'.join(a)
def tick(t):
    a=[]
    if re.search(r'\bCVBI11\b',t,re.I): a.append('CVBI11')
    if re.search(r'\bPCIP11\b',t,re.I): a.append('PCIP11')
    if CNPJ in re.sub(r'\D','',t) and 'PCIP11' not in a: a.append('PCIP11')
    return a
def dates(t):
    a=[]
    pats=[r'\b([0-3]\d)[/.-]([0-1]\d)[/.-](20\d{2})\b',r'\b(20\d{2})[-.]([0-1]\d)[-.]([0-3]\d)\b']
    for p in pats:
        for m in re.finditer(p,t):
            if len(m.group(1))==4: y,mo,d=map(int,m.groups())
            else: d,mo,y=map(int,m.groups())
            if 1900<=y<=2100 and 1<=mo<=12 and 1<=d<=31: a.append(f'{y:04d}-{mo:02d}-{d:02d}')
    return sorted(set(a))
def months(t):
    a=[]
    for m,n in MONTHS.items():
        for q in re.finditer(m+r'.{0,30}?((?:19|20)\d{2})',t,re.I): a.append(q.group(1)+'-'+n)
    return sorted(set(a))
def quarters(t):
    a=[]
    for p in [r'\b([1-4])T\s*((?:19|20)\d{2})\b',r'\b([1-4])T\s*(\d{2})\b']:
        for m in re.finditer(p,t,re.I):
            y=m.group(2); y='20'+y if len(y)==2 else y
            if 1900<=int(y)<=2100: a.append(y+'-T'+m.group(1))
    return sorted(set(a))
def enc(fn):
    a=[]
    for v in re.findall(r'(?:REL|ACE|FRV)(\d{8})V\d+',fn.upper()):
        d,mo,y=int(v[:2]),int(v[2:4]),int(v[4:8])
        if 1900<=y<=2100 and 1<=mo<=12 and 1<=d<=31: a.append(f'{y:04d}-{mo:02d}-{d:02d}')
    return sorted(set(a))
def sig(t):
    l=t.lower(); has=lambda z:any(x in l for x in z)
    return {'D':has(['distribui','rendimentos','amortiza','rendimento por cota']),'N':has(['valor patrimonial','patrimônio líquido','patrimonio liquido','valor da cota','cota patrimonial']),'P':has(['cri','certificados de recebíveis imobiliários','certificados de recebiveis imobiliarios','carteira','ativos']),'R':has(['resultado distribuível','resultado distribuivel','resultado financeiro','resultado do fundo','receitas','despesas']),'E':has(['fato relevante','assembleia','emissão de cotas','emissao de cotas','alteração do nome','alteracao do nome','reorganização societária','reorganizacao societaria'])}
def main():
    p=Path(sys.argv[1]); s=p.suffix.lower()
    if s=='.pdf': t=pdf(p)
    elif s=='.xml': t=xml(p)
    elif s=='.zip': t=zipx(p)
    elif s in ['.xlsx','.xlsm','.xltx','.xltm']: t=xlsx(p)
    elif s in ['.txt','.csv']: t=p.read_text(encoding='utf-8',errors='replace')
    else: print('STATUS=UNSUPPORTED_EXTENSION'); return
    t=clean(t); q=sig(t); tk=tick(t); per=['DATE:'+x for x in enc(p.name)]+['MONTH:'+x for x in months(p.name+' '+t)]+['QUARTER:'+x for x in quarters(p.name+' '+t)]
    print('STATUS=EXTRACTED'); print('TEXT_LENGTH='+str(len(t))); print('CONTENT_TICKER='+','.join(tk)); print('CNPJ_SIGNAL='+str(CNPJ in re.sub(r'\D','',t))); print('CONTENT_PERIODS='+'|'.join(sorted(set(per)))); print('CONTENT_DATES='+'|'.join(dates(t)[:50])); print('CONTENT_QUARTERS='+'|'.join(quarters(t))); print('CONTENT_MONTHS='+'|'.join(months(t))); print('DISTRIBUTION_SIGNAL='+str(q['D'])); print('NAV_SIGNAL='+str(q['N'])); print('PORTFOLIO_SIGNAL='+str(q['P'])); print('RESULT_SIGNAL='+str(q['R'])); print('EVENT_SIGNAL='+str(q['E']))
try: main()
except Exception as e: print('STATUS=EXTRACTOR_ERROR'); print('ERROR_TYPE='+type(e).__name__); print('ERROR_MESSAGE='+str(e).replace('\n',' '))
'@
Set-Content -LiteralPath $TempPy -Value $ExtractorCode -Encoding UTF8
Write-Host "[4/8] Extracting content..."
$resultRows=New-Object 'System.Collections.Generic.List[object]'; $counter=0
foreach($row in $uniqueRows){
    $counter++; $filePath=Join-Path $Repo ([string]$row.RelativePath); $displayName=[string]$row.Original_FileName; if([string]::IsNullOrWhiteSpace($displayName)){$displayName=[string]$row.FileName}; if([string]::IsNullOrWhiteSpace($displayName)){$displayName=[IO.Path]::GetFileName($filePath)}; if([string]::IsNullOrWhiteSpace($displayName)){$displayName="Document_$counter"};
    Write-Progress -Activity "PCIP11 multi-format extraction" -Status $displayName -PercentComplete ([math]::Round(($counter/$uniqueRows.Count)*100,1))
    $ext=[IO.Path]::GetExtension($filePath).ToLowerInvariant(); $status="";$ct="";$cj="";$per="";$dt="";$qt="";$mo="";$ds="";$ns="";$ps="";$rs="";$es="";$et="";$em="";$tl="0"
    if(-not(Test-Path -LiteralPath $filePath)){ $status='FILE_NOT_FOUND';$et='PATH_ERROR';$em='File not found' } else { try {
        $psi=New-Object Diagnostics.ProcessStartInfo; $psi.FileName=$pythonExe; $psi.Arguments='"'+$TempPy+'" "'+$filePath+'"'; $psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
        $proc=New-Object Diagnostics.Process; $proc.StartInfo=$psi; [void]$proc.Start(); $stdout=$proc.StandardOutput.ReadToEnd(); $stderr=$proc.StandardError.ReadToEnd(); $proc.WaitForExit();
        if($stdout -match '(?m)^STATUS=(.*)$'){$status=$Matches[1].Trim()}else{$status='NO_STATUS'}
        $map=@{'TEXT_LENGTH'='tl';'CONTENT_TICKER'='ct';'CNPJ_SIGNAL'='cj';'CONTENT_PERIODS'='per';'CONTENT_DATES'='dt';'CONTENT_QUARTERS'='qt';'CONTENT_MONTHS'='mo';'DISTRIBUTION_SIGNAL'='ds';'NAV_SIGNAL'='ns';'PORTFOLIO_SIGNAL'='ps';'RESULT_SIGNAL'='rs';'EVENT_SIGNAL'='es';'ERROR_TYPE'='et';'ERROR_MESSAGE'='em'}
        foreach($k in $map.Keys){ if($stdout -match ('(?m)^'+$k+'=(.*)$')){ Set-Variable -Name $map[$k] -Value $Matches[1].Trim() } }
        if($status -eq 'EXTRACTOR_ERROR' -and [string]::IsNullOrWhiteSpace($em) -and -not [string]::IsNullOrWhiteSpace($stderr)){$em=($stderr -replace '\s+',' ').Trim()}
        $proc.Dispose()
    } catch {$status='POWERSHELL_EXCEPTION';$et=$_.Exception.GetType().Name;$em=$_.Exception.Message} }
    $resultRows.Add([pscustomobject]@{Historical_ID=[string]$row.Historical_ID;SHA256=[string]$row.SHA256;FileName=$displayName;RelativePath=[string]$row.RelativePath;Extension=$ext;Original_Ticker=[string]$row.Historical_Ticker;Content_Ticker=$ct;CNPJ_Signal=$cj;Storage_Year=[string]$row.Storage_Year;Document_Year=[string]$row.Document_Year;Document_Period_Manifest=[string]$row.Document_Period;Content_Periods=$per;Content_Dates=$dt;Content_Quarters=$qt;Content_Months=$mo;Canonical_Type=[string]$row.Canonical_Type;Priority=[string]$row.Priority;Extraction_Status=$status;Text_Length=$tl;Distribution_Signal=$ds;NAV_Signal=$ns;Portfolio_Signal=$ps;Result_Signal=$rs;Event_Signal=$es;Error_Type=$et;Error_Message=$em})
}
Write-Progress -Activity "PCIP11 multi-format extraction" -Completed
$resultRows|Sort-Object Storage_Year,Canonical_Type,FileName|Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8
$total=$resultRows.Count;$extracted=@($resultRows|?{$_.Extraction_Status -eq 'EXTRACTED'}).Count;$errors=$total-$extracted;$pdf=@($resultRows|?{$_.Extension -eq '.pdf'}).Count;$xml=@($resultRows|?{$_.Extension -eq '.xml'}).Count;$zip=@($resultRows|?{$_.Extension -eq '.zip'}).Count;$xlsx=@($resultRows|?{$_.Extension -in '.xlsx','.xlsm','.xltx','.xltm'}).Count;$cvbi=@($resultRows|?{$_.Content_Ticker -match 'CVBI11'}).Count;$pcip=@($resultRows|?{$_.Content_Ticker -match 'PCIP11'}).Count;$cnpj=@($resultRows|?{$_.CNPJ_Signal -eq 'True'}).Count;$dist=@($resultRows|?{$_.Distribution_Signal -eq 'True'}).Count;$nav=@($resultRows|?{$_.NAV_Signal -eq 'True'}).Count;$port=@($resultRows|?{$_.Portfolio_Signal -eq 'True'}).Count;$res=@($resultRows|?{$_.Result_Signal -eq 'True'}).Count;$evt=@($resultRows|?{$_.Event_Signal -eq 'True'}).Count
$lines=@("# 0695.2R3 FIXED - PCIP11 Multi-format Content Extraction","","Status: MULTI-FORMAT TRIAGE COMPLETED","Period: 2024-2026","Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')","","## Processing","","- Manifest rows: $($manifestRows.Count)","- Unique physical documents: $total","- Extracted: $extracted","- Errors: $errors","","## Formats","","- PDF: $pdf","- XML: $xml","- ZIP: $zip","- XLSX/XLSM/XLTX/XLTM: $xlsx","","## Identity","","- CVBI11 found in content: $cvbi","- PCIP11 found in content: $pcip","- CNPJ found in content: $cnpj","","## Signals","","- Distribution: $dist","- NAV/PL: $nav","- Portfolio: $port","- Result: $res","- Events: $evt","","## Extraction statuses","")
foreach($g in @($resultRows|Group-Object Extraction_Status|Sort-Object Name)){$lines += "- $($g.Name): $($g.Count)"}
$lines += @("","## Safety","","- No Vault note modified.","- No asset note modified.","- No metric promoted.","- No source document modified.","","## Outputs","","- CSV: $OutputCsv","- Report: $OutputMd","","## Status","","0695.2R3 FIXED MULTI-FORMAT EXTRACTION COMPLETED")
$lines|Set-Content -LiteralPath $OutputMd -Encoding UTF8;Remove-Item -LiteralPath $TempPy -Force -ErrorAction SilentlyContinue
Write-Host "";Write-Host "============================================================";Write-Host "0695.2R3 FIXED - FINAL VALIDATION";Write-Host "============================================================";Write-Host "Unique physical : $total";Write-Host "Extracted       : $extracted";Write-Host "Errors          : $errors";Write-Host "PDF             : $pdf";Write-Host "XML             : $xml";Write-Host "ZIP             : $zip";Write-Host "XLSX            : $xlsx";Write-Host "PCIP11 content  : $pcip";Write-Host "CNPJ content    : $cnpj";Write-Host "Distribution    : $dist";Write-Host "NAV/PL          : $nav";Write-Host "Portfolio       : $port";Write-Host "Result          : $res";Write-Host "Events          : $evt";Write-Host "";Write-Host "CSV              : $OutputCsv";Write-Host "Report           : $OutputMd";Write-Host "";Write-Host "STATUS: 0695.2R3 FIXED MULTI-FORMAT EXTRACTION COMPLETED";Write-Host "============================================================"
