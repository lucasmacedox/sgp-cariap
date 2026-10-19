"""Conversão entre os modelos do domínio e o JSON trocado com a interface.

Cada campo de dataclass declara, em ``metadata``, a chave usada no JSON e o
conversor que normaliza o valor recebido. ``Modelo.de_dict`` aplica esses
conversores e ignora chaves desconhecidas, o que mantém compatíveis os arquivos
exportados por versões anteriores.

Exemplo::

    @dataclass
    class Produto(Modelo):
        grupo_fiscal: str = campo("grupofiscal")
        valor: Decimal | None = campo(conversor=dinheiro, padrao=None)
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar
from collections.abc import Callable

from .dinheiro import para_decimal

Conversor = Callable[[Any], Any]
M = TypeVar("M", bound="Modelo")

_CHAVE = "chave_json"
_CONVERSOR = "conversor"


# --- conversores ------------------------------------------------------------

def texto(valor: Any) -> str:
    return "" if valor is None else " ".join(str(valor).split())


def texto_livre(valor: Any) -> str:
    """Texto de várias linhas: mantém as quebras e só apara as pontas."""
    return "" if valor is None else str(valor).replace("\r\n", "\n").strip()


def dinheiro(valor: Any) -> Decimal | None:
    return para_decimal(valor)


def inteiro(valor: Any) -> int | None:
    numero = para_decimal(valor)
    return None if numero is None else int(numero)


def booleano(valor: Any) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in ("1", "true", "sim", "on")
    return bool(valor)


def lista_de_texto(valor: Any) -> list[str]:
    if not isinstance(valor, (list, tuple)):
        return []
    return [t for t in (texto(v) for v in valor) if t]


def lista_de(tipo: type[M]) -> Conversor:
    """Conversor para listas de submodelos."""
    def converter(valor: Any) -> list[M]:
        if not isinstance(valor, (list, tuple)):
            return []
        return [tipo.de_dict(v) for v in valor if isinstance(v, dict)]
    return converter


def enumeracao(tipo: type[Enum], padrao: Enum) -> Conversor:
    def converter(valor: Any) -> Enum:
        try:
            return tipo(valor)
        except ValueError:
            return padrao
    return converter


# --- declaração de campos ---------------------------------------------------

_SEM_PADRAO = object()


def campo(chave: str | None = None, *, conversor: Conversor = texto,
          padrao: Any = _SEM_PADRAO, fabrica: Callable[[], Any] | None = None) -> Any:
    """Declara um campo serializável.

    ``chave`` é o nome no JSON quando difere do atributo. Sem ``padrao`` nem
    ``fabrica``, o padrão é ``conversor(None)`` (texto vazio, lista vazia etc.).
    """
    metadata = {_CHAVE: chave, _CONVERSOR: conversor}
    if fabrica is not None:
        return dataclasses.field(default_factory=fabrica, metadata=metadata)
    if padrao is _SEM_PADRAO:
        vazio = conversor(None)
        if isinstance(vazio, list):
            return dataclasses.field(default_factory=list, metadata=metadata)
        padrao = vazio
    return dataclasses.field(default=padrao, metadata=metadata)


def _chave(f: dataclasses.Field) -> str:
    return f.metadata.get(_CHAVE) or f.name


def _para_json(valor: Any) -> Any:
    if isinstance(valor, Modelo):
        return valor.para_dict()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, list):
        return [_para_json(v) for v in valor]
    return valor


class Modelo:
    """Base das dataclasses do domínio com leitura e escrita em JSON."""

    @classmethod
    def de_dict(cls: type[M], dados: dict | None) -> M:
        dados = dados or {}
        valores = {}
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]  # subclasses são dataclasses
            chave = _chave(f)
            if chave in dados:
                conversor = f.metadata.get(_CONVERSOR, texto)
                valores[f.name] = conversor(dados[chave])
        return cls(**valores)

    def para_dict(self) -> dict:
        return {_chave(f): _para_json(getattr(self, f.name)) for f in dataclasses.fields(self)}  # type: ignore[arg-type]
