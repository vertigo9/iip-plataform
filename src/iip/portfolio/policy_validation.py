"""Validação de faixa compartilhada entre contratos de política.

``target_policy.py`` (alvo por ativo) e ``class_budget.py`` (alvo por classe) usam a MESMA
regra de faixa -- ``min <= alvo <= max`` e ``alvo ± tolerância`` cabendo dentro de
``[min, max]`` -- por isso ela vive aqui uma vez só, em vez de duplicada nos dois contratos.
Levanta ``ValueError`` com o motivo; nunca há fallback silencioso.
"""

from __future__ import annotations

import math


def fail(label: str, reason: str) -> ValueError:
    return ValueError(f"linha {label!r}: {reason}")


def check_number(label: str, field_name: str, value: float | None, high: float) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise fail(label, f"{field_name} precisa ser um número")
    if not math.isfinite(value) or not 0 <= value <= high:
        raise fail(label, f"{field_name}={value} fora do intervalo 0 a {high:g}")


def check_target_range(
    label: str,
    target: float | None,
    tolerance: float | None,
    low: float | None,
    high: float | None,
) -> None:
    """``min <= alvo <= max`` e a faixa ``alvo ± tolerância`` cabe dentro de ``[min, max]``."""
    if low is not None and high is not None and low > high:
        raise fail(label, f"min_pct ({low:g}) maior que max_pct ({high:g})")
    if target is not None and low is not None and target < low:
        raise fail(label, f"alvo ({target:g}) abaixo do mínimo ({low:g})")
    if target is not None and high is not None and target > high:
        raise fail(label, f"alvo ({target:g}) acima do máximo ({high:g})")
    if target is not None and tolerance is not None:
        if low is not None and target - tolerance < low:
            raise fail(
                label,
                f"a faixa (alvo - tolerância = {target - tolerance:g}) fica abaixo do "
                f"mínimo ({low:g})",
            )
        if high is not None and target + tolerance > high:
            raise fail(
                label,
                f"a faixa (alvo + tolerância = {target + tolerance:g}) passa do máximo "
                f"({high:g})",
            )
