from pathlib import Path

path = Path("src/iip/portfolio/matrix.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

text = path.read_text(encoding="utf-8")

old = """from .registry import (
    FUND_MANAGERS,
    ProviderStatus,
    manifest_map,
)
"""
new = """from iip.providers.registry import (
    FUND_MANAGERS,
    ProviderStatus,
    manifest_map,
)
"""

if old not in text:
    raise SystemExit(
        "Import antigo não encontrado em src/iip/portfolio/matrix.py; "
        "nenhuma alteração foi feita."
    )

path.write_text(text.replace(old, new), encoding="utf-8")
print("FIX1 aplicado: portfolio.matrix usa o provider registry real.")
