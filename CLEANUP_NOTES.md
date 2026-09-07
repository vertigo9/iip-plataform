# Pacote limpo

Esta distribuição contém a árvore ativa do projeto, testes, documentação, dados de exemplo e o vault atual. Foram removidos do artefato distribuível o histórico `.git`, caches Python, relatórios gerados, `archive/`, instaladores, arquivos compactados, backups e scripts identificados como quebrados ou históricos.

O arquivo `scripts/ops/setup_iip.py` foi excluído da distribuição porque contém uma string tripla não encerrada e falha na compilação. O arquivo original não foi alterado; revise-o separadamente antes de reintroduzi-lo.

A validação executada nesta cópia foi:

```bash
PYTHONPATH=src python3 -m compileall -q -f src tests patria_harvester_patch patria_harvester_patch_v4 scripts examples
```

O comando acima passou para a árvore ativa. A suíte `pytest` ainda requer instalação das dependências de desenvolvimento declaradas no `pyproject.toml`.
