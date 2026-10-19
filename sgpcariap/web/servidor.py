"""Servidor HTTP local: entrega a interface e encaminha ``/api/*`` para a API.

Escuta apenas em 127.0.0.1 e recusa requisições com cabeçalho ``Host`` ou
``Origin`` de outro endereço, o que impede que páginas abertas no navegador
usem o assistente sem o usuário saber.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..erros import ErroAssistente
from .api import ApiAssistente, RotaInexistente

ENDERECO = "127.0.0.1"
_HOSTS_LOCAIS = {"127.0.0.1", "localhost"}
_TENTATIVAS_DE_PORTA = 20
_MAX_CORPO = 5 * 1024 * 1024  # a maior requisição é a configuração do provedor, de poucos KB

log = logging.getLogger(__name__)

# Só recursos do próprio assistente; a página não pode ser aberta dentro de outro site.
_POLITICA_CONTEUDO = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                      "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                      "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/woff2", ".woff2")


class _ServidorHTTP(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, porta: int, api: ApiAssistente, estaticos: Path):
        super().__init__((ENDERECO, porta), _Manipulador)
        self.api = api
        self.estaticos = estaticos.resolve()


class _Manipulador(BaseHTTPRequestHandler):
    server: _ServidorHTTP
    server_version = "SGPCariap"

    def log_message(self, formato, *args):
        if not self.path.startswith("/api/job"):
            log.debug("%s %s", self.address_string(), formato % args)

    # --- entrada ------------------------------------------------------------------

    def do_GET(self):
        if not self._origem_local():
            return
        if self.path.startswith("/api/"):
            self._api("GET", {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})
        else:
            self._arquivo(urlparse(self.path).path)

    def do_POST(self):
        if not self._origem_local():
            return
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if not 0 <= tamanho <= _MAX_CORPO:
                return self._json(413, {"erro": "requisição grande demais"})
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"erro": "JSON inválido"})
        self._api("POST", dados if isinstance(dados, dict) else {})

    # --- processamento ----------------------------------------------------------------

    def _origem_local(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        origem = self.headers.get("Origin")
        if host not in _HOSTS_LOCAIS or (origem and urlparse(origem).hostname not in _HOSTS_LOCAIS):
            self._json(403, {"erro": "acesso permitido apenas a partir deste computador"})
            return False
        return True

    def _api(self, metodo: str, dados: dict) -> None:
        caminho = urlparse(self.path).path
        try:
            self._json(200, self.server.api.despachar(metodo, caminho, dados))
        except RotaInexistente as erro:
            self._json(404, {"erro": str(erro)})
        except ErroAssistente as erro:
            self._json(400, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001 - a interface mostra a mensagem
            log.exception("falha em %s %s", metodo, caminho)
            self._json(500, {"erro": f"falha interna ({type(erro).__name__}: {erro})"})

    def _arquivo(self, caminho: str) -> None:
        raiz = self.server.estaticos
        alvo = (raiz / (caminho.lstrip("/") or "index.html")).resolve()
        if raiz not in alvo.parents or not alvo.is_file():
            return self._json(404, {"erro": "não encontrado"})
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo == "application/json":
            tipo += "; charset=utf-8"
        self._responder(200, alvo.read_bytes(), tipo, cache="no-cache")

    def _json(self, status: int, corpo: dict) -> None:
        self._responder(status, json.dumps(corpo, ensure_ascii=False).encode(),
                        "application/json; charset=utf-8", cache="no-store")

    def _responder(self, status: int, conteudo: bytes, tipo: str, cache: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(conteudo)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", _POLITICA_CONTEUDO)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(conteudo)


class ServidorAssistente:
    """Sobe o servidor na primeira porta livre a partir de ``porta``."""

    def __init__(self, api: ApiAssistente, estaticos: Path, porta: int = 8765):
        self._servidor = self._abrir(api, estaticos, porta)

    @staticmethod
    def _abrir(api: ApiAssistente, estaticos: Path, porta: int) -> _ServidorHTTP:
        for candidata in range(porta, porta + _TENTATIVAS_DE_PORTA):
            try:
                return _ServidorHTTP(candidata, api, estaticos)
            except OSError:
                continue
        raise OSError(f"nenhuma porta livre entre {porta} e {porta + _TENTATIVAS_DE_PORTA - 1}")

    @property
    def porta(self) -> int:
        return self._servidor.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{ENDERECO}:{self.porta}/"

    def servir(self) -> None:
        self._servidor.serve_forever()

    def encerrar(self) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()
