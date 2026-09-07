
$file = "tests\test_coverage_core_export.py"
$content = Get-Content $file -Raw
$content = $content.Replace('assert "Asset Symbol,CPFE3" in result', 'assert ''"Asset Symbol",CPFE3'' in result')
Set-Content $file $content -Encoding UTF8
Write-Host "Patched CSV assertion."
