"""Live fetch of the most recent Pátria "Planilha de Fundamentos" for
a given ticker -- finds the right MZIQ category from
``iip.sources.patria_mziq.PATRIA_MZIQ_FUNDS`` (by matching "planilha"
+ "fundamentos" in a category's internal name, never hardcoding the
exact per-fund slug string a second time here), lists its documents
for the most recent year, downloads the newest one, and parses it with
``iip.sources.patria_planilha_fundamentos.parse_resumo_tijolo``.

Three real HTTP round-trips per call (years lookup, document listing,
file download) -- reuses ``MziqHTTPHarvester`` for the first two (same
transport as every other MZIQ document flow in this project) and a
plain unauthenticated GET for the third, same as
``iip.cli.main._collect_mziq_manager_documents`` already does for
every other MZIQ document type.
"""

from __future__ import annotations

import io
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .mziq import MziqDocument, build_documents_target, build_years_target
from .mziq_harvester import MziqHTTPHarvester
from .patria_mziq import fund_for_ticker
from .patria_planilha_fundamentos import FundamentosPlanilha, parse_resumo_tijolo


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _planilha_category(category_internal_names: tuple[str, ...]) -> str | None:
    for name in category_internal_names:
        normalized = _normalize(name)
        if "planilha" in normalized and "fundamento" in normalized:
            return name
    return None


@dataclass(frozen=True)
class FetchedPlanilhaFundamentos:
    ticker: str
    category: str
    document: MziqDocument | None
    fundamentos: FundamentosPlanilha | None


class PatriaPlanilhaFundamentosHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 60.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent
        self._mziq = MziqHTTPHarvester(opener=self._opener, user_agent=user_agent)

    def _download(self, url: str) -> bytes:
        request = Request(
            url,
            headers={"User-Agent": self.user_agent},
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        return response.read()

    def fetch(self, ticker: str) -> FetchedPlanilhaFundamentos:
        """Raises ``ValueError`` if the ticker has no registered Pátria
        MZIQ config or no "planilha de fundamentos"-style category --
        a real configuration gap, not something to silently skip.
        Returns ``document=None``/``fundamentos=None`` (not an
        exception) when the category exists but genuinely has no
        published documents yet, or when the sheet doesn't match the
        "tijolo" layout (e.g. a credit fund) -- both real, expected
        outcomes a caller should handle, not error paths.
        """

        fund = fund_for_ticker(ticker)
        if fund is None:
            raise ValueError(f"no Patria MZIQ config registered for ticker {ticker!r}")

        category = _planilha_category(fund.category_internal_names)
        if category is None:
            raise ValueError(
                f"no 'planilha de fundamentos' category registered for {ticker!r}"
            )

        years = self._mziq.fetch_years(
            build_years_target(fund.company_id, (category,))
        )
        if not years:
            return FetchedPlanilhaFundamentos(
                ticker=ticker.upper(), category=category, document=None, fundamentos=None
            )

        latest_year = max(years)
        documents = self._mziq.fetch_documents(
            build_documents_target(fund.company_id, latest_year, (category,))
        )
        documents_with_url = tuple(d for d in documents if d.url)
        if not documents_with_url:
            return FetchedPlanilhaFundamentos(
                ticker=ticker.upper(), category=category, document=None, fundamentos=None
            )

        latest_document = max(
            documents_with_url, key=lambda d: d.file_date or ""
        )

        body = self._download(latest_document.url)
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(body), data_only=True)
        fundamentos = parse_resumo_tijolo(workbook, ticker)

        return FetchedPlanilhaFundamentos(
            ticker=ticker.upper(),
            category=category,
            document=latest_document,
            fundamentos=fundamentos,
        )
