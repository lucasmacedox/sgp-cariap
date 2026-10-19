"""Dublês de teste compartilhados."""

from __future__ import annotations

from dataclasses import dataclass, field

from sgpcariap.cadastro import NivelLog
from sgpcariap.dominio import Configuracao
from sgpcariap.sgp import ListaOpcoes, Opcao


def opcoes(*rotulos: str, campo: str = "") -> ListaOpcoes:
    return ListaOpcoes([Opcao("", "---------")] + [Opcao(str(i), r) for i, r in enumerate(rotulos, 1)],
                       campo=campo)


@dataclass
class ObservadorMemoria:
    atualizacoes: list[tuple[int, str]] = field(default_factory=list)
    mensagens: list[tuple[str, NivelLog]] = field(default_factory=list)

    def passo_atualizado(self, indice: int, passo) -> None:
        self.atualizacoes.append((indice, passo.para_dict()["situacao"]))

    def registrar(self, mensagem: str, nivel: NivelLog = NivelLog.INFO) -> None:
        self.mensagens.append((mensagem, nivel))


def configuracao_exemplo(**alteracoes) -> Configuracao:
    """Dois grupos: 400 e 600 MEGA recebem dois livros; 1GB recebe um."""
    dados = {
        "provedor": "Teste",
        "grupos": [
            {"nome": "Essencial", "planos": ["Fibra - 400 MEGA", "Fibra - 600 MEGA"],
             "servicos": ["E-book Super Essencial", "Audiobook Super Duo"]},
            {"nome": "Premium", "planos": ["Fibra - 1GB"], "servicos": ["E-book Super Duo"]},
        ],
        "lote": {"pausa_segundos": 0},
    }
    dados.update(alteracoes)
    return Configuracao.de_dict(dados)
