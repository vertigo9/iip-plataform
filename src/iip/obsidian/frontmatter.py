"""Linhas de cabeçalho YAML para as notas que o painel lê.

JSON em uma linha é YAML válido (estilo de fluxo) e escapa sozinho aspas, dois-pontos e
acentos, então listas de objetos cabem numa chave sem montar YAML na mão.
"""

from __future__ import annotations

import json
from typing import Any


def flow_line(key: str, value: Any) -> str:
    return f"{key}: {json.dumps(value, ensure_ascii=False)}"
