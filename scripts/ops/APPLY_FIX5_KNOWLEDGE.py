from pathlib import Path
import re

path = Path("tests/test_coverage_knowledge_health.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

text = path.read_text(encoding="utf-8")

text = text.replace(
    'assert "CPFE3" in repo.read_markdown("03_Decisions", "DEC-CPFE3-1")',
    'assert "CPFE3" in dpath.read_text(encoding="utf-8")',
)
text = text.replace(
    'assert "fact" in repo.read_markdown("04_Evidence", "EV-1")',
    'assert "fact" in epath.read_text(encoding="utf-8")',
)

if 'repo.read_markdown("03_Decisions", "DEC-CPFE3-1")' in text:
    raise SystemExit("A primeira API read_markdown ainda está presente.")
if 'repo.read_markdown("04_Evidence", "EV-1")' in text:
    raise SystemExit("A segunda API read_markdown ainda está presente.")

path.write_text(text, encoding="utf-8")
print("FIX5 aplicado com sucesso.")
