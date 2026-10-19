"""Sessão HTTP com cookies, usando apenas a biblioteca padrão.

Evitar dependências externas mantém o assistente instalável em qualquer
máquina com Python e simplifica o empacotamento em executável.

A sessão mantém uma única conexão aberta com o SGP (keep-alive): cada página
do SGP já custa perto de um segundo para ser gerada, e abrir uma conexão TLS
nova a cada requisição somaria mais um décimo de segundo a cada uma delas.

Leituras (GET) que falham por oscilação de rede ou por resposta 502/503/504
são repetidas algumas vezes, com espera crescente. Envios (POST) nunca são
repetidos automaticamente, para não gravar o mesmo cadastro duas vezes.
"""

from __future__ import annotations

import http.client
import socket
import ssl
import time
import urllib.parse
from dataclasses import dataclass, field
from email.message import Message
from collections.abc import Callable, Iterable

from ..erros import ErroCertificado, ErroConexao

_AGENTE = "Mozilla/5.0 (sgp-cariap)"
_REDIRECIONAMENTOS = (301, 302, 303, 307, 308)
_INSTAVEIS = (502, 503, 504)
_MAX_REDIRECIONAMENTOS = 10


@dataclass(frozen=True)
class Resposta:
    status: int
    url: str
    texto: str
    cabecalhos: Message
    conteudo: bytes = b""
    """Corpo original, para arquivos (exportações em Excel)."""

    @property
    def redirecionamento(self) -> str | None:
        if self.status in _REDIRECIONAMENTOS:
            return self.cabecalhos.get("Location", "")
        return None


@dataclass(frozen=True)
class PoliticaRepeticao:
    """Quantas vezes repetir uma leitura que falhou e quanto esperar antes de cada uma."""

    esperas: tuple[float, ...] = (1.0, 3.0)
    dormir: Callable[[float], None] = field(default=time.sleep, compare=False)


SEM_REPETICAO = PoliticaRepeticao(esperas=())


def normalizar_url(url: str) -> str:
    """Remove espaços e barra final e assume HTTPS quando falta o esquema."""
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def criar_contexto_ssl(verificar: bool) -> ssl.SSLContext:
    """Contexto TLS; usa as autoridades do ``certifi`` quando disponível.

    No executável empacotado e no Python oficial do macOS, o sistema não fornece
    as autoridades certificadoras ao ``ssl``; o ``certifi`` cobre esses casos.
    """
    if not verificar:
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
        return contexto
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class Cookies:
    """Cookies de um único servidor (o SGP usa ``csrftoken`` e ``sessionid``)."""

    def __init__(self):
        self._valores: dict[str, str] = {}

    def get(self, nome: str) -> str | None:
        return self._valores.get(nome)

    def receber(self, cabecalhos: Message) -> None:
        for linha in cabecalhos.get_all("Set-Cookie") or []:
            par, *partes = linha.split(";")
            nome, _, valor = par.strip().partition("=")
            if not nome:
                continue
            atributos = {a.strip().split("=", 1)[0].lower(): a.strip() for a in partes}
            expirou = atributos.get("max-age", "").lower() in ("max-age=0", "max-age=-1") or (
                "expires" in atributos and "1970" in atributos["expires"])
            if expirou or valor in ('""', ""):
                self._valores.pop(nome, None)
            else:
                self._valores[nome] = valor.strip('"')

    def cabecalho(self) -> str:
        return "; ".join(f"{nome}={valor}" for nome, valor in self._valores.items())


class SessaoHTTP:
    """Requisições a um único servidor, com cookies e conexão reaproveitada."""

    def __init__(self, url_base: str, *, timeout: float = 60, verificar_ssl: bool = True,
                 repeticao: PoliticaRepeticao | None = None):
        self.url_base = normalizar_url(url_base)
        partes = urllib.parse.urlsplit(self.url_base)
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise ErroConexao(f"endereço inválido: {url_base}")
        self._https = partes.scheme == "https"
        self._host, self._porta = partes.hostname, partes.port
        self._prefixo = partes.path  # SGP publicado num subcaminho
        self.timeout = timeout
        self._contexto = criar_contexto_ssl(verificar_ssl) if self._https else None
        self._repeticao = repeticao or PoliticaRepeticao()
        self._conexao: http.client.HTTPConnection | None = None
        self._cookies = Cookies()
        self.requisicoes = 0
        """Total de requisições feitas (para medir o custo de cada operação)."""

    def cookie(self, nome: str) -> str | None:
        return self._cookies.get(nome)

    def get(self, caminho: str, *, timeout: float | None = None) -> Resposta:
        """``timeout`` vale só para esta leitura (exportações grandes demoram mais)."""
        if timeout is None:
            return self._seguir("GET", caminho, None, seguir=True)
        anterior = self.timeout
        self._mudar_timeout(timeout)
        try:
            return self._seguir("GET", caminho, None, seguir=True)
        finally:
            self._mudar_timeout(anterior)

    def post(self, caminho: str, dados: Iterable[tuple[str, str]], *, seguir: bool = False) -> Resposta:
        """Envia um formulário. Por padrão não segue o redirecionamento, que no
        Django indica sucesso e é tratado por quem chamou."""
        return self._seguir("POST", caminho, list(dados), seguir=seguir)

    def fechar(self) -> None:
        if self._conexao is not None:
            self._conexao.close()
            self._conexao = None

    # --- internos ---------------------------------------------------------------------

    def _mudar_timeout(self, segundos: float) -> None:
        self.timeout = segundos
        if self._conexao is not None:
            self._conexao.timeout = segundos
            if self._conexao.sock is not None:
                self._conexao.sock.settimeout(segundos)

    def _seguir(self, metodo: str, caminho: str, dados: list | None, *, seguir: bool) -> Resposta:
        resposta = self._requisitar(metodo, caminho, dados)
        for _ in range(_MAX_REDIRECIONAMENTOS):
            destino = resposta.redirecionamento
            if not seguir or destino is None:
                return resposta
            # depois de um POST, o navegador segue o redirecionamento com GET
            resposta = self._requisitar("GET", self._caminho_de(destino), None)
        raise ErroConexao(f"{self.url_base}{caminho} redirecionou vezes demais")

    def _caminho_de(self, destino: str) -> str:
        """Caminho relativo à URL base a partir de um ``Location`` absoluto ou relativo."""
        partes = urllib.parse.urlsplit(urllib.parse.urljoin(self.url_base + "/", destino))
        caminho = partes.path + (f"?{partes.query}" if partes.query else "")
        if self._prefixo and caminho.startswith(self._prefixo):
            caminho = caminho[len(self._prefixo):]
        return caminho

    def _requisitar(self, metodo: str, caminho: str, dados: list | None) -> Resposta:
        esperas = iter(self._repeticao.esperas if metodo == "GET" else ())
        while True:
            try:
                resposta = self._uma_requisicao(metodo, caminho, dados)
            except ErroCertificado:
                raise
            except ErroConexao:
                espera = next(esperas, None)
                if espera is None:
                    raise
                self._repeticao.dormir(espera)
                continue
            if resposta.status in _INSTAVEIS:
                espera = next(esperas, None)
                if espera is not None:
                    self._repeticao.dormir(espera)
                    continue
            return resposta

    def _uma_requisicao(self, metodo: str, caminho: str, dados: list | None) -> Resposta:
        url = self.url_base + caminho
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        cabecalhos = {"User-Agent": _AGENTE, "Referer": url, "Accept-Encoding": "identity"}
        if self._cookies.cabecalho():
            cabecalhos["Cookie"] = self._cookies.cabecalho()
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        # Uma conexão parada pode ter sido fechada pelo servidor sem aviso. Na leitura,
        # vale repetir uma vez com conexão nova. No envio não dá para saber se o SGP
        # gravou antes de a conexão cair; por isso o envio sempre abre uma conexão
        # nova e nunca é repetido (repetir poderia gravar o serviço duas vezes).
        if metodo != "GET":
            self.fechar()
        for tentativa in (1, 2):
            reaproveitada = self._conexao is not None
            conexao = self._abrir()
            try:
                self.requisicoes += 1
                conexao.request(metodo, self._prefixo + caminho, body=corpo, headers=cabecalhos)
                r = conexao.getresponse()
                conteudo = r.read()
            except (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError) as erro:
                self.fechar()
                if reaproveitada and tentativa == 1 and metodo == "GET":
                    continue
                raise self._traduzir(erro) from erro
            except (OSError, http.client.HTTPException) as erro:
                self.fechar()
                raise self._traduzir(erro) from erro
            if r.getheader("Connection", "").lower() == "close":
                self.fechar()
            self._cookies.receber(r.msg)
            return Resposta(r.status, url, conteudo.decode("utf-8", "replace"), r.msg, conteudo)
        raise AssertionError("inalcançável")

    def _abrir(self) -> http.client.HTTPConnection:
        if self._conexao is None:
            if self._https:
                self._conexao = http.client.HTTPSConnection(
                    self._host, self._porta, timeout=self.timeout, context=self._contexto)
            else:
                self._conexao = http.client.HTTPConnection(self._host, self._porta, timeout=self.timeout)
        return self._conexao

    def _traduzir(self, erro: Exception) -> ErroConexao:
        if isinstance(erro, ssl.SSLCertVerificationError) or (
                isinstance(erro, ssl.SSLError) and "CERTIFICATE" in str(erro).upper()):
            return ErroCertificado(
                f"certificado HTTPS de {self.url_base} não pôde ser verificado; se for um SGP "
                "interno, marque “aceitar certificado não verificado”")
        if isinstance(erro, (socket.timeout, TimeoutError)):
            return ErroConexao(f"{self.url_base} demorou mais de {self.timeout:.0f} s para responder")
        return ErroConexao(f"não foi possível acessar {self.url_base}: {erro}")
