# IIP Development Setup Script

Write-Host "Setting up IIP Platform development environment..." -ForegroundColor Cyan

# Install dependencies
pip install -e ".[dev]"

Write-Host ""
Write-Host "Development environment ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Yellow
Write-Host "  python -m iip.cli.main version" -ForegroundColor White
Write-Host "  python -m iip.cli.main health" -ForegroundColor White
Write-Host "  python -m pytest -v" -ForegroundColor White
Write-Host "  python -m pytest --cov=iip" -ForegroundColor White
