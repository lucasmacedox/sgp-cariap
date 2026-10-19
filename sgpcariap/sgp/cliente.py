"""Sessão autenticada no SGP."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable, Mapping

from ..erros import ErroAutenticacao, ErroFormulario, ErroPermissao, ErroSGP
from .formulario import Formulario, ValorCampo, extrair_erros
from .http import Resposta, SessaoHTTP

_ROTA_LOGIN = "/accounts/login/"
_VERSAO = re.compile(r"Ver\.\s*(\d+(?:\.\d+)+)")
_CSRF = re.compile(r"""name=['"]csrfmiddlewaretoken['"]\s+value=['"]([^'"]+)""")


class _SessaoExpirada(Exception):
    pass


class ClienteSGP:
    """Sessão autenticada. Se expirar, entra de novo uma vez com a senha guardada em memória."""

    def __init__(self, sessao: SessaoHTTP, usuario: str, senha: str = ""):
        self._sessao = sessao
        self.usuario = usuario
        self._senha = senha
        self._trava = threading.Lock()
        self.versao_sgp = ""

    @classmethod
    def conectar(cls, url: str, usuario: str, senha: str, *,
                 verificar_ssl: bool = True, timeout: float = 60) -> ClienteSGP:
        cliente = cls(SessaoHTTP(url, timeout=timeout, verificar_ssl=verificar_ssl), usuario, senha)
        cliente._entrar()
        return cliente

    @property
    def url(self) -> str:
        return self._sessao.url_base

    def _entrar(self) -> None:
        pagina = self._sessao.get(_ROTA_LOGIN)
        if pagina.status >= 400:
            raise ErroSGP(f"{self.url}{_ROTA_LOGIN} respondeu HTTP {pagina.status}; "
                          "confira se o endereço é de um SGP")
        dados = [("username", self.usuario), ("password", self._senha), ("next", "/admin/")]
        token = self._token_csrf(pagina.texto)
        if token:
            dados.append(("csrfmiddlewaretoken", token))
        resposta = self._sessao.post(_ROTA_LOGIN, dados, seguir=True)
        if _ROTA_LOGIN.rstrip("/") in resposta.url:
            raise ErroAutenticacao("login recusado: confira usuário e senha")
        achado = _VERSAO.search(resposta.texto)
        self.versao_sgp = achado.group(1) if achado else self.versao_sgp

    def _token_csrf(self, html: str = "") -> str | None:
        achado = _CSRF.search(html)
        return achado.group(1) if achado else self._sessao.cookie("csrftoken")

    def _com_sessao(self, operacao):
        with self._trava:
            try:
                return operacao()
            except _SessaoExpirada:
                if not self._senha:
                    raise ErroAutenticacao("a sessão no SGP expirou; conecte de novo") from None
                self._entrar()
            try:
                return operacao()
            except _SessaoExpirada:
                raise ErroAutenticacao("a sessão no SGP expirou e o novo login não foi aceito; "
                                       "conecte de novo") from None

    def pagina(self, caminho: str) -> str:
        return self._com_sessao(lambda: self._ler(caminho).texto)

    def pagina_e_endereco(self, caminho: str) -> tuple[str, str]:
        resposta = self._com_sessao(lambda: self._ler(caminho))
        return resposta.texto, resposta.url

    def arquivo(self, caminho: str, *, timeout: float | None = None) -> Resposta:
        return self._com_sessao(lambda: self._ler(caminho, timeout))

    def _ler(self, caminho: str, timeout: float | None = None) -> Resposta:
        resposta = self._sessao.get(caminho, timeout=timeout)
        self._verificar_acesso(resposta, caminho)
        if resposta.status >= 400:
            raise ErroSGP(f"{caminho} respondeu HTTP {resposta.status}")
        return resposta

    def formulario(self, caminho: str) -> Formulario:
        return Formulario.de_html(self.pagina(caminho))

    def enviar(self, caminho: str, alteracoes: Mapping[str, ValorCampo],
               extras: Iterable[tuple[str, str]] = (),
               formulario: Formulario | None = None) -> str:
        """Envia o formulário de ``caminho`` e devolve o destino do redirecionamento."""
        reaproveitar = formulario

        def enviar_uma_vez() -> str:
            nonlocal reaproveitar
            atual = reaproveitar or Formulario.de_html(self._ler(caminho).texto)
            reaproveitar = None
            dados = atual.preencher(alteracoes, extras)
            if not any(nome == "csrfmiddlewaretoken" for nome, _ in dados):
                token = self._token_csrf()
                if token:
                    dados.append(("csrfmiddlewaretoken", token))
            resposta = self._sessao.post(caminho, dados)
            destino = resposta.redirecionamento
            if destino is not None:
                if _ROTA_LOGIN.rstrip("/") in destino:
                    raise _SessaoExpirada
                return destino
            self._verificar_acesso(resposta, caminho)
            raise ErroFormulario(extrair_erros(resposta.texto), resposta.status)

        return self._com_sessao(enviar_uma_vez)

    @staticmethod
    def _verificar_acesso(resposta: Resposta, caminho: str) -> None:
        if _ROTA_LOGIN.rstrip("/") in resposta.url:
            raise _SessaoExpirada
        if resposta.status == 403:
            raise ErroPermissao(f"o usuário não tem acesso a {caminho}")
