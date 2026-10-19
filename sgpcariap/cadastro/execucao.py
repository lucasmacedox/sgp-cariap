"""Tipos comuns às execuções acompanhadas pela interface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class NivelLog(str, Enum):
    INFO = "info"
    SUCESSO = "ok"
    ERRO = "erro"


class ObservadorExecucao(Protocol):
    """Recebe o andamento da execução (tela, arquivo de registro, testes)."""

    def passo_atualizado(self, indice: int, passo: Any) -> None:
        """``passo`` tem ``para_dict()``."""

    def registrar(self, mensagem: str, nivel: NivelLog = NivelLog.INFO) -> None: ...


@dataclass(frozen=True)
class ResumoExecucao:
    concluidos: int
    pulados: int
    erros: int

    @property
    def sucesso(self) -> bool:
        return self.erros == 0
