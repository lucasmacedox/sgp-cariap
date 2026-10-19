"""Tipos compartilhados pelas execuções."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class NivelLog(str, Enum):
    INFO = "info"
    SUCESSO = "ok"
    ERRO = "erro"


class ObservadorExecucao(Protocol):
    def passo_atualizado(self, indice: int, passo: Any) -> None: ...

    def registrar(self, mensagem: str, nivel: NivelLog = NivelLog.INFO) -> None: ...


@dataclass(frozen=True)
class ResumoExecucao:
    concluidos: int
    erros: int

    @property
    def sucesso(self) -> bool:
        return self.erros == 0
