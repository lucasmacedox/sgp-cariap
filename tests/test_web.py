import http.client
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from sgpcariap.ambiente import Ambiente
from sgpcariap.cadastro import AssistenteCadastro
from sgpcariap.erros import ErroAssistente, ErroEstado
from sgpcariap.web import ApiAssistente, ServidorAssistente
from sgpcariap.web.api import RotaInexistente



class _Ambiente:
    def __init__(self, pasta: Path):
        self.ambiente = Ambiente(recursos=pasta / "static", dados=pasta / "dados", versao="teste")


class _CatalogoFalso:
    cliente = SimpleNamespace(url="https://sgp.exemplo", usuario="robo")

    def atualizar(self):
        pass

    def resumo(self):
        return {"planos_internet": [{"rotulo": "Fibra - 400 MEGA"}], "planos_servico": []}


def _api(pasta: Path) -> ApiAssistente:
    return ApiAssistente(_Ambiente(pasta).ambiente,
                         conectar=lambda url, usuario, senha, verificar_ssl: AssistenteCadastro(_CatalogoFalso()))


class TestApi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_rotas_registradas(self):
        api = _api(self.pasta)
        with self.assertRaises(RotaInexistente):
            api.despachar("GET", "/api/nada", {})
        self.assertEqual(api.despachar("GET", "/api/status", {})["conectado"], False)

    def test_operacoes_exigem_conexao(self):
        with self.assertRaises(ErroEstado):
            _api(self.pasta).despachar("POST", "/api/lote/montar", {"config": {}})

    def test_conectar_valida_os_campos(self):
        with self.assertRaises(ErroAssistente):
            _api(self.pasta).despachar("POST", "/api/conectar", {"url": "x", "usuario": "", "senha": ""})

    def test_planos_e_lote_exigem_conexao(self):
        api = _api(self.pasta)
        for metodo, caminho in (("GET", "/api/planos"), ("POST", "/api/lote/montar"), ("GET", "/api/lote/opcoes")):
            with self.subTest(caminho=caminho), self.assertRaises(ErroEstado):
                api.despachar(metodo, caminho, {"config": {}})

    def test_planos_vem_do_catalogo(self):
        api = _api(self.pasta)
        api.despachar("POST", "/api/conectar", {"url": "x", "usuario": "u", "senha": "s"})
        self.assertEqual(api.despachar("GET", "/api/planos", {})["planos_internet"][0]["rotulo"], "Fibra - 400 MEGA")

    def test_nao_desconecta_nem_troca_de_sgp_durante_a_execucao(self):
        api = _api(self.pasta)
        api.despachar("POST", "/api/conectar", {"url": "x", "usuario": "u", "senha": "s"})
        api._tarefas.em_andamento = lambda: True
        for caminho, dados in (("/api/desconectar", {}), ("/api/conectar", {"url": "y", "usuario": "u", "senha": "s"})):
            with self.subTest(caminho=caminho), self.assertRaises(ErroEstado):
                api.despachar("POST", caminho, dados)
        self.assertTrue(api.despachar("GET", "/api/status", {})["conectado"])

    def test_controle_de_tarefa_inexistente(self):
        with self.assertRaises(ErroAssistente):
            _api(self.pasta).despachar("POST", "/api/job/controle", {"id": "nada", "acao": "pausar"})


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        pasta = Path(cls._tmp.name)
        (pasta / "static").mkdir()
        (pasta / "static" / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")
        (pasta / "segredo.txt").write_text("não deve sair", encoding="utf-8")
        cls.servidor = ServidorAssistente(_api(pasta), pasta / "static", porta=18765)
        threading.Thread(target=cls.servidor.servir, daemon=True).start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.servidor.encerrar()
        cls._tmp.cleanup()

    def _get(self, caminho, cabecalhos=None, corpo=None):
        requisicao = urllib.request.Request(self.servidor.url.rstrip("/") + caminho, headers=cabecalhos or {},
                                            data=corpo)
        try:
            with urllib.request.urlopen(requisicao, timeout=5) as r:
                self.cabecalhos = r.headers
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            self.cabecalhos = e.headers
            return e.code, e.read().decode()

    def test_cabecalhos_de_seguranca(self):
        self._get("/")
        self.assertIn("frame-ancestors 'none'", self.cabecalhos["Content-Security-Policy"])
        self.assertEqual((self.cabecalhos["X-Frame-Options"], self.cabecalhos["X-Content-Type-Options"]),
                         ("DENY", "nosniff"))

    def test_recusa_corpo_grande_demais(self):
        # só o cabeçalho: o servidor recusa sem ler o corpo
        conexao = http.client.HTTPConnection("127.0.0.1", self.servidor.porta, timeout=5)
        conexao.putrequest("POST", "/api/conectar")
        conexao.putheader("Content-Length", str(6 * 1024 * 1024))
        conexao.endheaders()
        self.assertEqual(conexao.getresponse().status, 413)
        conexao.close()

    def test_entrega_a_pagina(self):
        self.assertEqual(self._get("/"), (200, "<h1>ok</h1>"))

    def test_nao_sai_da_pasta_de_estaticos(self):
        self.assertEqual(self._get("/../segredo.txt")[0], 404)

    def test_api_responde_json(self):
        status, corpo = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(corpo)["versao"], "teste")

    def test_recusa_origem_externa(self):
        self.assertEqual(self._get("/api/status", {"Origin": "https://site-qualquer.com"})[0], 403)
        self.assertEqual(self._get("/api/status", {"Host": "evil.example"})[0], 403)


if __name__ == "__main__":
    unittest.main()
