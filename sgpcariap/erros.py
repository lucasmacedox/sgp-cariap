"""Exceções com mensagem pronta para o usuário."""

from __future__ import annotations


class ErroAssistente(Exception):
    pass


class ErroSGP(ErroAssistente):
    pass


class ErroConexao(ErroSGP):
    pass


class ErroCertificado(ErroConexao):
    pass


class ErroAutenticacao(ErroSGP):
    pass


class ErroPermissao(ErroSGP):
    pass


class ErroFormulario(ErroSGP):
    def __init__(self, mensagens: list[str], status: int | None = None):
        self.mensagens = mensagens
        self.status = status
        texto = "; ".join(mensagens) if mensagens else f"o SGP recusou o envio (HTTP {status})"
        super().__init__(texto)


class ErroOpcao(ErroAssistente):
    pass


class OpcaoNaoEncontrada(ErroOpcao):
    def __init__(self, campo: str, texto: str):
        super().__init__(f'{campo}: opção "{texto}" não existe neste SGP')


class OpcaoAmbigua(ErroOpcao):
    def __init__(self, campo: str, texto: str, quantidade: int):
        super().__init__(
            f'{campo}: "{texto}" corresponde a {quantidade} opções; use o texto completo'
        )


class ErroPlanoIndisponivel(ErroSGP):
    """Plano fora do POP do contrato."""


class ErroIdentificacao(ErroSGP):
    """Serviço gravado, mas sem ID para ativar."""


class ErroAtivacao(ErroSGP):
    pass


class ErroEstado(ErroAssistente):
    pass
