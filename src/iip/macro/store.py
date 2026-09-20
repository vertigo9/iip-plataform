"""Persistência versionada das séries macro, uma por indicador, no vault.

Arquivo ``07_Research/Macro/series/<indicador>.json``. É APPEND-ONLY no sentido que importa:
uma observação nunca é editada nem apagada. Quando uma coleta traz, para uma competência que
já existe, um valor DIFERENTE do último guardado (a fonte revisou, ou o mês em curso andou),
grava-se uma nova observação com a nova data de coleta, e a anterior continua lá. Um valor
igual ao último guardado não gera linha (senão cada coleta diária duplicaria a série).

Isto dá duas leituras:
  - ``latest``: o valor mais recente de cada competência (o que se sabe hoje);
  - ``as_known_on(data)``: o valor de cada competência COMO ERA CONHECIDO na data, usando só as
    observações coletadas até ela. Só vale a partir da primeira coleta (``first_collected_at``):
    a fonte não informa quando publicou cada valor, então o que veio antes de começarmos a
    coletar não tem data de conhecimento.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from iip.macro.contract import MacroObservation

STORE_RELATIVE_PATH = Path("07_Research") / "Macro" / "series"
RUNS_RELATIVE_PATH = Path("07_Research") / "Macro" / "_coleta.json"


@dataclass(frozen=True)
class IngestResult:
    new: int  # competências que não existiam
    revised: int  # competências cujo valor mudou desde a última coleta
    unchanged: int


class MacroStore:
    def __init__(self, vault_path: str | Path) -> None:
        self.vault = Path(vault_path)
        self.root = self.vault / STORE_RELATIVE_PATH

    def path_for(self, indicator_id: str) -> Path:
        return self.root / f"{indicator_id}.json"

    def observations(self, indicator_id: str) -> tuple[MacroObservation, ...]:
        """Todas, na ordem em que foram gravadas (competência, depois data de coleta)."""
        try:
            payload = json.loads(
                self.path_for(indicator_id).read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError):
            return ()
        return tuple(
            MacroObservation(**item) for item in payload.get("observations", ())
        )

    def _write(self, indicator_id: str, observations: list[MacroObservation]) -> None:
        path = self.path_for(indicator_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(observations, key=lambda o: (o.reference, o.collected_at))
        payload = {
            "type": "macro_series",
            "indicator": indicator_id,
            "observations": [asdict(o) for o in ordered],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def ingest(
        self,
        indicator_id: str,
        points: tuple[tuple[str, float | None, bool], ...],
        *,
        collected_at: str,
        notes: dict[str, str] | None = None,
    ) -> IngestResult:
        """``points``: (competência, valor, provisório). Devolve o que entrou de novo, o que
        foi revisado e o que já estava igual."""
        existing = list(self.observations(indicator_id))
        latest_by_ref: dict[str, MacroObservation] = {}
        for obs in existing:  # já em ordem: a última de cada competência vence
            latest_by_ref[obs.reference] = obs
        new = revised = unchanged = 0
        for reference, value, provisional in points:
            before = latest_by_ref.get(reference)
            if before is None:
                new += 1
            elif before.value == value and before.provisional == provisional:
                unchanged += 1
                continue
            else:
                revised += 1
            added = MacroObservation(
                indicator_id,
                reference,
                value,
                collected_at,
                provisional,
                (notes or {}).get(reference, ""),
            )
            existing.append(added)
            latest_by_ref[reference] = added
        if new or revised:
            self._write(indicator_id, existing)
        return IngestResult(new, revised, unchanged)

    def latest(self, indicator_id: str) -> tuple[MacroObservation, ...]:
        """O valor mais recente de cada competência, da mais antiga à mais nova."""
        by_ref: dict[str, MacroObservation] = {}
        for obs in self.observations(indicator_id):
            by_ref[obs.reference] = obs
        return tuple(by_ref[r] for r in sorted(by_ref))

    def as_known_on(self, indicator_id: str, when: str) -> tuple[MacroObservation, ...]:
        """Cada competência com o valor conhecido em ``when`` (AAAA-MM-DD): só entram
        observações coletadas até essa data. Vazio antes da primeira coleta."""
        by_ref: dict[str, MacroObservation] = {}
        for obs in self.observations(indicator_id):
            if obs.collected_at <= when:
                by_ref[obs.reference] = obs
        return tuple(by_ref[r] for r in sorted(by_ref))

    def revisions(self, indicator_id: str) -> tuple[tuple[MacroObservation, ...], ...]:
        """As competências que tiveram mais de um valor: cada uma como a sequência de
        observações, da primeira à última."""
        history: dict[str, list[MacroObservation]] = {}
        for obs in self.observations(indicator_id):
            history.setdefault(obs.reference, []).append(obs)
        return tuple(tuple(v) for _, v in sorted(history.items()) if len(v) > 1)

    def first_collected_at(self, indicator_id: str) -> str | None:
        stamps = [o.collected_at for o in self.observations(indicator_id)]
        return min(stamps) if stamps else None

    def last_collected_at(self, indicator_id: str) -> str | None:
        stamps = [o.collected_at for o in self.observations(indicator_id)]
        return max(stamps) if stamps else None

    # --- o registro das coletas: quando cada indicador foi consultado, mesmo que nada mudou ---

    def runs(self) -> dict[str, dict]:
        try:
            return json.loads(
                (self.vault / RUNS_RELATIVE_PATH).read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def record_run(
        self,
        indicator_id: str,
        *,
        collected_at: str,
        status: str,
        result: IngestResult | None = None,
        detail: str = "",
    ) -> None:
        """Anota a coleta (com sucesso ou não). ``last_ok`` só anda quando deu certo, para a
        nota poder dizer "consultado há N dias" sem confundir com a última tentativa."""
        runs = self.runs()
        entry = dict(runs.get(indicator_id, {}))
        entry.update(
            {
                "last_attempt": collected_at,
                "status": status,
                "detail": detail,
                "new": result.new if result else 0,
                "revised": result.revised if result else 0,
            }
        )
        if status == "ok":
            entry["last_ok"] = collected_at
        runs[indicator_id] = entry
        path = self.vault / RUNS_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8"
        )
