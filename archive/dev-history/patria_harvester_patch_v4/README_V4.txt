PATCH V4 — Patria Harvester

Correções:
- anos antigos: não depende exclusivamente de <select>; tenta também controles visíveis e texto exato do ano;
- links antigos da Patria/MZIQ: aceita api.mziq.com/mzfilemanager/ mesmo sem extensão .pdf;
- em --headed, quando um ano não for localizado, mantém o navegador aberto por 3 segundos para diagnóstico;
- preserva a lógica que já funcionou em 2025/2026;
- valida sintaxe antes de gravar o arquivo e cria backup automático.

INSTALAÇÃO (na raiz do projeto):
python .\patria_harvester_patch_v4.py

Depois:
python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2019 --headed
python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2023 --headed

Se 2019 e 2023 funcionarem, rode a coleta completa:
python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2019-2026 --headed
