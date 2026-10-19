"""Classificação das falhas do lote. Falhas gerais afetariam todos os contratos seguintes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..erros import (ErroAtivacao, ErroAutenticacao, ErroConexao, ErroFormulario, ErroIdentificacao, ErroOpcao,
                     ErroPermissao, ErroPlanoIndisponivel)


class Causa(str, Enum):
    CONEXAO = "conexao"
    SESSAO = "sessao"
    PERMISSAO = "permissao"
    POP = "pop"
    CADASTRO = "cadastro"
    OPCAO = "opcao"
    ATIVACAO = "ativacao"
    IDENTIFICACAO = "identificacao"
    OUTRA = "outra"


@dataclass(frozen=True)
class Diagnostico:
    titulo: str
    orientacao: str
    geral: bool = False


DIAGNOSTICOS: dict[Causa, Diagnostico] = {
    Causa.CONEXAO: Diagnostico("SGP sem resposta", "Confira a internet e se o SGP abre no navegador.", geral=True),
    Causa.SESSAO: Diagnostico("Sessão recusada", "Conecte de novo na etapa Conexão.", geral=True),
    Causa.PERMISSAO: Diagnostico("Sem permissão", "Dê ao usuário acesso a contratos e serviços de TV.", geral=True),
    Causa.POP: Diagnostico("Plano fora do POP", "Inclua o POP do contrato no cadastro do plano de TV."),
    Causa.CADASTRO: Diagnostico("Recusado pelo SGP", "Confira CPF, e-mail, celular e endereço do cliente."),
    Causa.OPCAO: Diagnostico("Opção não encontrada", "Confira o grupo TV e o modo de aquisição nas opções do SGP."),
    Causa.ATIVACAO: Diagnostico("Não ativou", "Confira o cadastro do cliente e se o contrato está ativo."),
    Causa.IDENTIFICACAO: Diagnostico("Serviço sem ID", "O serviço foi gravado; ative pelo SGP."),
    Causa.OUTRA: Diagnostico("Erro inesperado", "Veja a mensagem e o registro da execução."),
}

# da mais específica para a mais genérica
_POR_TIPO: tuple[tuple[type[Exception], Causa], ...] = (
    (ErroPlanoIndisponivel, Causa.POP),
    (ErroIdentificacao, Causa.IDENTIFICACAO),
    (ErroAtivacao, Causa.ATIVACAO),
    (ErroAutenticacao, Causa.SESSAO),
    (ErroPermissao, Causa.PERMISSAO),
    (ErroConexao, Causa.CONEXAO),
    (ErroFormulario, Causa.CADASTRO),
    (ErroOpcao, Causa.OPCAO),
)


@dataclass(frozen=True)
class Falha:
    servico: str
    causa: Causa
    mensagem: str

    @property
    def diagnostico(self) -> Diagnostico:
        return DIAGNOSTICOS[self.causa]

    @property
    def geral(self) -> bool:
        return self.diagnostico.geral

    def para_dict(self) -> dict:
        return {"servico": self.servico, "causa": self.causa.value, "mensagem": self.mensagem,
                "titulo": self.diagnostico.titulo, "orientacao": self.diagnostico.orientacao,
                "geral": self.geral}


def classificar(erro: Exception, servico: str = "") -> Falha:
    causa = next((c for tipo, c in _POR_TIPO if isinstance(erro, tipo)), Causa.OUTRA)
    return Falha(servico, causa, str(erro) or type(erro).__name__)

