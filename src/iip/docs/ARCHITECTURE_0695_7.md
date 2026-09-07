# Arquitetura 0695.7

## Camadas

```text
0695.2–0695.6
   |
   v
Historical Evidence
   |
   v
Semantic Identity Resolution
   |
   v
MetricObservationIdentity
   |
   +--> exact duplicate
   |       |
   |       v
   |   dedupe/idempotency
   |
   +--> semantic distinct
           |
           v
       semantic dimension
           |
           v
       stable Observation Key
           |
           v
       Metric Evidence ID
           |
           v
       Knowledge Evidence ID
           |
           v
       KnowledgeBridge adapter
           |
           v
          Vault
```

## Separação de responsabilidades

### `metric_identity.py`

Responsável por:

- definir a identidade semântica;
- resolver dimensão com contexto local;
- classificar duplicata;
- preservar linhagem.

Não persiste nada.

### `metric_persistence.py`

Responsável por:

- criar IDs estáveis;
- construir a representação de Knowledge Evidence;
- aplicar regras puras de agrupamento/idempotência.

Não escreve no Vault.

### `metric_persistence_adapter.py`

Responsável por:

- adaptar CSV histórico para o domínio;
- preparar persistência;
- oferecer fake bridge para testes;
- manter a execução real desligada.

### Scripts

Orquestram execução e relatórios, sem modificar dados históricos.

### Tests

Validam especialmente os defeitos encontrados durante o 0695.7:

- duplicação de 78,18;
- distinção 13,40/13,09;
- dimensão semântica;
- linhagem CVBI11 -> PCIP11;
- IDs estáveis;
- idempotência.

## Princípio de compatibilidade

O pacote foi desenhado como extensão. A estrutura existente de:

```text
iip.knowledge.models
iip.knowledge.bridge
iip.knowledge.repository
```

permanece como contrato de destino.

O adapter deve ser integrado ao contrato existente em vez de substituir o `KnowledgeBridge`.
