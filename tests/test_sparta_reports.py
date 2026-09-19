from iip.sources.sparta_reports import (
    _extract_cota_patrimonial_from_text,
    build_target,
)

# Captured live (17/09/2026) via pypdf's layout-mode extraction of the
# real CRAA11 March/2026 report page 2 (sparta.com.br/uploads/
# CRAA11_RelatorioMensal_2026_03.pdf) -- not synthesized. Confirms the
# fund's own reported "Cota patrimonial" was R$ 101,64 that month,
# independently cross-checked against a web search summary of the same
# PDF quoting the same figure.
_REAL_DESTAQUES_BLOCK = """ DESTAQUES DO MÊS
  R$ 101,64                                   R$ 1,25                                      15,6%
            Cota patrimonial                      Última distribuição                      Dividend Yield (12m)

 R$ 0,7 milhão                                    +90%                               CDI +          1,6%
           Liquidez média                        das empresas faturam                  Carrego da carteira (a.a.)
             diária na B3                          acima de R$ 1,0 bi                     em CDI equivalente
"""


def test_extracts_cota_patrimonial_from_real_captured_layout():
    value = _extract_cota_patrimonial_from_text(_REAL_DESTAQUES_BLOCK)
    assert value == 101.64


def test_returns_none_when_heading_absent():
    assert _extract_cota_patrimonial_from_text("nothing relevant here") is None


def test_returns_none_when_label_absent():
    text = "DESTAQUES DO MÊS\nsome other stat box entirely\n"
    assert _extract_cota_patrimonial_from_text(text) is None


def test_picks_the_column_aligned_value_not_just_the_first_one():
    # Same shape as the real block, but with "Cota patrimonial" moved to
    # the second column -- the nearer value (R$ 1,25) must be picked,
    # not R$ 101,64 (which would be wrong if this just took index 0).
    text = (
        " DESTAQUES DO MÊS\n"
        "  R$ 101,64                                   R$ 1,25\n"
        "            Outra coisa                          Cota patrimonial\n"
    )
    value = _extract_cota_patrimonial_from_text(text)
    assert value == 1.25


def test_build_target_matches_confirmed_live_url_pattern():
    target = build_target("craa11", 2026, 3)
    assert (
        target.url == "https://sparta.com.br/uploads/CRAA11_RelatorioMensal_2026_03.pdf"
    )
    assert target.ticker == "CRAA11"


def test_build_target_rejects_invalid_month():
    try:
        build_target("CRAA11", 2026, 13)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_target_rejects_empty_ticker():
    try:
        build_target("", 2026, 3)
        assert False, "expected ValueError"
    except ValueError:
        pass
