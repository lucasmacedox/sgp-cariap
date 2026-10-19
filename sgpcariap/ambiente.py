"""Caminhos e parâmetros do ambiente de execução."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import __version__

VARIAVEL_DADOS = "SGP_CARIAP_DADOS"
VARIAVEL_RETENCAO = "SGP_CARIAP_RETENCAO_DIAS"
RETENCAO_PADRAO = 90
_PACOTE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Ambiente:
    """Onde ficam os arquivos da interface e os dados gerados pelo assistente.

    ``recursos`` aponta para ``sgpcariap/static``. No executável gerado pelo
    PyInstaller essa pasta é extraída junto com o pacote, então o mesmo caminho
    relativo vale nos dois casos.
    """

    recursos: Path
    dados: Path
    versao: str = __version__
    retencao_dias: int = RETENCAO_PADRAO
    """Dias que os registros das execuções ficam guardados (0: para sempre)."""

    @classmethod
    def detectar(cls) -> Ambiente:
        dados = os.environ.get(VARIAVEL_DADOS) or Path.home() / "SGP-Cariap"
        retencao = os.environ.get(VARIAVEL_RETENCAO, "").strip()
        return cls(recursos=_PACOTE / "static", dados=Path(dados),
                   retencao_dias=int(retencao) if retencao.isdigit() else RETENCAO_PADRAO)

    @property
    def execucoes(self) -> Path:
        return self.dados / "execucoes"
