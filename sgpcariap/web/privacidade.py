"""Dados pessoais nos registros gravados em disco (LGPD).

Os registros das execuções servem para auditoria: o que foi feito em cada
contrato. CPF/CNPJ, telefone e e-mail do cliente não são necessários para isso
e ficam mascarados; o nome do cliente e o número do contrato ficam, porque é
por eles que o operador confere o que aconteceu no SGP.
"""

from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")
# sequências de dígitos com 8 ou mais algarismos, com ou sem pontuação: CPF, CNPJ, telefone
_NUMERO = re.compile(r"\+?\(?\d[\d().\s/-]{6,}\d")

_CAMPOS_TEXTO = ("detalhe", "msg", "mensagem")


def mascarar(texto: str) -> str:
    """"(84) 99999-0001" → "***0001"; "fulano@gmail.com" → "f***@gmail.com"."""
    texto = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", texto)

    def numero(achado: re.Match) -> str:
        digitos = re.sub(r"\D", "", achado.group(0))
        return f"***{digitos[-4:]}" if len(digitos) >= 8 else achado.group(0)

    return _NUMERO.sub(numero, texto)


def anonimizar(valor: Any) -> Any:
    """Cópia de ``valor`` (dicts e listas) com os campos de texto livre mascarados."""
    if isinstance(valor, dict):
        return {chave: mascarar(v) if chave in _CAMPOS_TEXTO and isinstance(v, str) else anonimizar(v)
                for chave, v in valor.items()}
    if isinstance(valor, list):
        return [anonimizar(v) for v in valor]
    return valor
