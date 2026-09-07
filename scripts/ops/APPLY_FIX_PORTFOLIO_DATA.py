from pathlib import Path

path = Path("tests/test_coverage_low_risk_helpers.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

text = path.read_text(encoding="utf-8")
old = """def test_portfolio_data_public_contract():
    import iip.portfolio_data.models as module
    assert any(not n.startswith("_") for n in dir(module))
"""
new = """def test_portfolio_data_public_contract():
    import iip.portfolio_data as module
    assert any(not n.startswith("_") for n in dir(module))
"""
if old not in text:
    raise SystemExit("Contrato antigo de portfolio_data não encontrado.")
path.write_text(text.replace(old, new), encoding="utf-8")
print("FIX aplicado: portfolio_data usa o namespace público real.")
