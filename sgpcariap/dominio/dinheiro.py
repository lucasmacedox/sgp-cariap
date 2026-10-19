"""Valores monetários como ``Decimal``."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")

_NAO_NUMERICO = re.compile(r"[^\d,.\-]")


def para_decimal(valor: object) -> Decimal | None:
    """``119.99``, ``"119,99"`` ou ``"R$ 1.234,56"``; ``None`` se vazio ou não numérico."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return arredondar(valor)
    if isinstance(valor, (int, float)):
        return arredondar(Decimal(str(valor)))
    texto = _NAO_NUMERICO.sub("", str(valor)).strip("-")
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return arredondar(Decimal(texto))
    except InvalidOperation:
        return None


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
