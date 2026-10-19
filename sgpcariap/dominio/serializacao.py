"""Leitura dos modelos a partir do JSON da interface.

Cada campo declara o conversor do valor recebido; chaves desconhecidas são ignoradas,
o que mantém válidos arquivos de versões anteriores.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, TypeVar

from .dinheiro import para_decimal

Conversor = Callable[[Any], Any]
M = TypeVar("M", bound="Modelo")

_CONVERSOR = "conversor"


def texto(valor: Any) -> str:
    return "" if valor is None else " ".join(str(valor).split())


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
    def converter(valor: Any) -> list[M]:
        if not isinstance(valor, (list, tuple)):
            return []
        return [tipo.de_dict(v) for v in valor if isinstance(v, dict)]
    return converter


_SEM_PADRAO = object()


def campo(*, conversor: Conversor = texto, padrao: Any = _SEM_PADRAO, fabrica: Callable[[], Any] | None = None) -> Any:
    """Sem ``padrao`` nem ``fabrica``, o padrão é ``conversor(None)``."""
    metadata = {_CONVERSOR: conversor}
    if fabrica is not None:
        return dataclasses.field(default_factory=fabrica, metadata=metadata)
    if padrao is _SEM_PADRAO:
        vazio = conversor(None)
        if isinstance(vazio, list):
            return dataclasses.field(default_factory=list, metadata=metadata)
        padrao = vazio
    return dataclasses.field(default=padrao, metadata=metadata)


class Modelo:
    @classmethod
    def de_dict(cls: type[M], dados: dict | None) -> M:
        dados = dados or {}
        return cls(**{f.name: f.metadata[_CONVERSOR](dados[f.name])
                      for f in dataclasses.fields(cls) if f.name in dados})  # type: ignore[arg-type]
