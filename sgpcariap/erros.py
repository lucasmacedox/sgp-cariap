"""Hierarquia de exceções do assistente.

Toda exceção derivada de ``ErroAssistente`` carrega uma mensagem pronta para o
usuário final. A camada web devolve essas mensagens como estão; qualquer outra
exceção é tratada como falha interna.
"""

from __future__ import annotations


class ErroAssistente(Exception):
    """Erro esperado, com mensagem que pode ser exibida ao usuário."""


class ErroSGP(ErroAssistente):
    """Falha na comunicação com o SGP."""


class ErroConexao(ErroSGP):
    """O endereço do SGP não respondeu."""


class ErroCertificado(ErroConexao):
    """O certificado HTTPS do SGP não pôde ser verificado."""


class ErroAutenticacao(ErroSGP):
    """Usuário ou senha recusados, ou sessão expirada."""


class ErroPermissao(ErroSGP):
    """O usuário não tem acesso a uma tela necessária."""


class ErroFormulario(ErroSGP):
    """O SGP recusou o envio de um formulário."""

    def __init__(self, mensagens: list[str], status: int | None = None):
        self.mensagens = mensagens
        self.status = status
        texto = "; ".join(mensagens) if mensagens else f"o SGP recusou o envio (HTTP {status})"
        super().__init__(texto)


class ErroOpcao(ErroAssistente):
    """Um texto escolhido não corresponde a uma opção do formulário."""


class OpcaoNaoEncontrada(ErroOpcao):
    def __init__(self, campo: str, texto: str):
        super().__init__(f'{campo}: opção "{texto}" não existe neste SGP')


class OpcaoAmbigua(ErroOpcao):
    def __init__(self, campo: str, texto: str, quantidade: int):
        super().__init__(
            f'{campo}: "{texto}" corresponde a {quantidade} opções; use o texto completo'
        )


class ErroPlanoIndisponivel(ErroSGP):
    """O plano não aparece no formulário do contrato (sem o POP do contrato liberado)."""


class ErroIdentificacao(ErroSGP):
    """O serviço foi gravado, mas não foi possível descobrir o ID dele para ativar."""


class ErroAtivacao(ErroSGP):
    """O SGP aceitou o pedido de ativação, mas o serviço continuou inativo."""


class ErroEstado(ErroAssistente):
    """Operação pedida fora de ordem (por exemplo, buscar clientes sem conexão)."""
