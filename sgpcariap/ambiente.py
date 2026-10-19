from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import __version__

VARIAVEL_DADOS = "SGP_CARIAP_DADOS"
_PACOTE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Ambiente:
    recursos: Path
    dados: Path
    versao: str = __version__

    @classmethod
    def detectar(cls) -> Ambiente:
        dados = os.environ.get(VARIAVEL_DADOS) or Path.home() / "SGP-Cariap"
        return cls(recursos=_PACOTE / "static", dados=Path(dados))

    @property
    def execucoes(self) -> Path:
        return self.dados / "execucoes"
