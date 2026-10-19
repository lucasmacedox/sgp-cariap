"""Sessão HTTP e cliente do SGP contra um servidor local que imita o SGP."""

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from sgpcariap.erros import ErroAutenticacao, ErroConexao
from sgpcariap.sgp import ClienteSGP
from sgpcariap.sgp.http import PoliticaRepeticao, SessaoHTTP

LOGIN = '<form><input type="hidden" name="csrfmiddlewaretoken" value="tok"></form>'


class _SGPFalso(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # mantém a conexão aberta, como o SGP
    estado: dict = {}

    def log_message(self, *args):
        pass

    def _responder(self, status=200, corpo="", cabecalhos=()):
        dados = corpo.encode()
        self.send_response(status)
        for nome, valor in cabecalhos:
            self.send_header(nome, valor)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _logado(self):
        return f"sessionid={self.estado['sessao']}" in (self.headers.get("Cookie") or "")

    def do_GET(self):
        e = self.estado
        e["conexoes"].add(self.client_address)
        e["gets"] += 1
        if self.path.startswith("/accounts/login/"):
            return self._responder(200, LOGIN, [("Set-Cookie", "csrftoken=tok; Path=/")])
        if self.path == "/instavel/":
            e["instavel"] -= 1
            return self._responder(503 if e["instavel"] >= 0 else 200, "ok")
        if not self._logado():
            return self._responder(302, cabecalhos=[("Location", "/accounts/login/?next=" + self.path)])
        if self.path == "/admin/":
            return self._responder(200, "<footer>SGP Ver. 1.0.251</footer>")
        if self.path == "/redireciona/":
            return self._responder(302, cabecalhos=[("Location", "/admin/destino/")])
        return self._responder(200, f"pagina {self.path}")

    def do_POST(self):
        e = self.estado
        e["posts"] += 1
        e["conexoes"].add(self.client_address)
        corpo = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        if self.path == "/accounts/login/":
            if corpo.get("password") == [e["senha"]]:
                e["sessao"] += 1
                return self._responder(302, cabecalhos=[("Location", "/admin/"),
                                                        ("Set-Cookie", f"sessionid={e['sessao']}; Path=/")])
            return self._responder(200, LOGIN)
        if self.path == "/instavel/":
            return self._responder(503, "fora")
        if self.path == "/derruba/":  # gravou e caiu antes de responder
            self.close_connection = True
            return
        if not self._logado():
            return self._responder(302, cabecalhos=[("Location", "/accounts/login/?next=" + self.path)])
        return self._responder(302, cabecalhos=[("Location", "/admin/gravado/")])


class TestSessaoHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _SGPFalso)
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def setUp(self):
        _SGPFalso.estado = {"conexoes": set(), "gets": 0, "posts": 0, "instavel": 0, "sessao": 1, "senha": "s"}
        self.esperas = []
        self.politica = PoliticaRepeticao(esperas=(0.5, 1.5), dormir=self.esperas.append)

    def test_reaproveita_a_conexao_e_guarda_cookies(self):
        sessao = SessaoHTTP(self.url, repeticao=self.politica)
        sessao.get("/accounts/login/")
        sessao.get("/accounts/login/")
        self.assertEqual((sessao.cookie("csrftoken"), len(_SGPFalso.estado["conexoes"])), ("tok", 1))

    def test_get_instavel_e_repetido_com_espera_crescente(self):
        _SGPFalso.estado["instavel"] = 2
        resposta = SessaoHTTP(self.url, repeticao=self.politica).get("/instavel/")
        self.assertEqual((resposta.status, self.esperas), (200, [0.5, 1.5]))

    def test_post_nunca_e_repetido(self):
        resposta = SessaoHTTP(self.url, repeticao=self.politica).post("/instavel/", [("a", "1")])
        self.assertEqual((resposta.status, _SGPFalso.estado["posts"], self.esperas), (503, 1, []))

    def test_post_usa_conexao_nova_e_nao_repete_se_cair(self):
        sessao = SessaoHTTP(self.url, repeticao=self.politica)
        sessao.get("/accounts/login/")
        with self.assertRaises(ErroConexao):
            sessao.post("/derruba/", [("a", "1")])
        self.assertEqual((_SGPFalso.estado["posts"], len(_SGPFalso.estado["conexoes"])), (1, 2))

    def test_servidor_fora_do_ar_vira_erro_de_conexao(self):
        with self.assertRaises(ErroConexao):
            SessaoHTTP("http://127.0.0.1:9", timeout=2, repeticao=self.politica).get("/")
        self.assertEqual(self.esperas, [0.5, 1.5])

    def test_cliente_entra_de_novo_quando_a_sessao_expira(self):
        cliente = ClienteSGP(SessaoHTTP(self.url, repeticao=self.politica), "u", "s")
        cliente._entrar()
        _SGPFalso.estado["sessao"] = 7  # o SGP derrubou a sessão
        self.assertEqual(cliente.pagina("/admin/x/"), "pagina /admin/x/")
        self.assertEqual(cliente.enviar("/admin/form/", {"campo": "1"}), "/admin/gravado/")

    def test_le_a_versao_do_sgp_no_login(self):
        cliente = ClienteSGP(SessaoHTTP(self.url, repeticao=self.politica), "u", "s")
        cliente._entrar()
        self.assertEqual(cliente.versao_sgp, "1.0.251")

    def test_novo_login_recusado_vira_erro_de_sessao(self):
        cliente = ClienteSGP(SessaoHTTP(self.url, repeticao=self.politica), "u", "s")
        cliente._entrar()
        _SGPFalso.estado.update(sessao=7, senha="trocada")
        with self.assertRaises(ErroAutenticacao):
            cliente.pagina("/admin/x/")

    def test_arquivo_traz_o_conteudo_original_com_tempo_limite_proprio(self):
        sessao = SessaoHTTP(self.url, repeticao=self.politica)
        cliente = ClienteSGP(sessao, "u", "s")
        cliente._entrar()
        resposta = cliente.arquivo("/exporta/", timeout=300)
        self.assertEqual((resposta.conteudo, sessao.timeout), (b"pagina /exporta/", 60))

    def test_segue_redirecionamento_e_informa_o_endereco_final(self):
        cliente = ClienteSGP(SessaoHTTP(self.url, repeticao=self.politica), "u", "s")
        cliente._entrar()
        self.assertEqual(cliente.pagina_e_endereco("/redireciona/"), ("pagina /admin/destino/", f"{self.url}/admin/destino/"))


if __name__ == "__main__":
    unittest.main()
