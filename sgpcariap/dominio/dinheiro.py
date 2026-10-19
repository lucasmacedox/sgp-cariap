"""Conversão e formatação de valores monetários.

Os valores circulam como ``Decimal`` para que a soma dos itens de uma
composição feche exatamente no preço do plano, sem resíduos de ponto flutuante.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")
ZERO = Decimal("0")
CEM = Decimal("100")

_NAO_NUMERICO = re.compile(r"[^\d,.\-]")


def para_decimal(valor: object) -> Decimal | None:
    """Converte números e textos como ``119.99``, ``"119,99"`` ou ``"R$ 1.234,56"``.

    Devolve ``None`` quando o valor está vazio ou não é numérico.
    """
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


def formatar_br(valor: Decimal | None) -> str:
    """``Decimal("1234.5")`` → ``"1.234,50"``; ``None`` → ``"-"``."""
    if valor is None:
        return "-"
    inteiro, _, centavos = f"{arredondar(valor):,.2f}".partition(".")
    return f"{inteiro.replace(',', '.')},{centavos}"


def formatar_formulario_br(valor: Decimal | None) -> str:
    """Formato aceito pelos campos de preço do SGP: ``"1234,56"``."""
    return f"{arredondar(valor or ZERO):.2f}".replace(".", ",")


def formatar_formulario(valor: Decimal | None) -> str:
    """Formato aceito pelos campos numéricos do Django admin: ``"1234.56"``."""
    return f"{arredondar(valor or ZERO):.2f}"
