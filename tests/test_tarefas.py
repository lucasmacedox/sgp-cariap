"""Execuções em segundo plano: uma por vez, registro em disco e dados pessoais."""

import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sgpcariap.cadastro import NivelLog, ResumoExecucao
from sgpcariap.erros import ErroEstado
from sgpcariap.web.privacidade import anonimizar, mascarar
from sgpcariap.web.tarefas import GerenciadorTarefas, RegistroExecucoes, StatusTarefa, Tarefa


class _Passo:
    def __init__(self, situacao, msg=""):
        self.situacao, self.msg = situacao, msg

    def para_dict(self):
        return {"contrato": "2447", "cliente": "Fulano", "situacao": self.situacao, "msg": self.msg,
                "pendencias": [{"titulo": "Celular sem o 9", "detalhe": "(84) 9999-0001 → (84) 99999-0001"}]}


def _esperar(condicao, limite=5.0):
    fim = time.monotonic() + limite
    while not condicao():
        if time.monotonic() > fim:
            raise AssertionError("tempo esgotado")
        time.sleep(0.01)


class TestPrivacidade(unittest.TestCase):
    def test_mascara_documento_telefone_e_email(self):
        self.assertEqual(mascarar("123.456.789-09"), "***8909")
        self.assertEqual(mascarar("(84) 99999-0001 → (84) 999990001"), "***0001 → ***0001")
        self.assertEqual(mascarar("fulano.tal@gmail.com"), "f***@gmail.com")

    def test_preserva_contrato_horario_e_endereco(self):
        texto = "Contrato 2447 (Fulano) às 10:19:59 em http://10.0.0.15:8000"
        self.assertEqual(mascarar(texto), texto)

    def test_anonimizar_so_mexe_nos_campos_de_texto(self):
        dados = anonimizar(_Passo("erro", "CPF 123.456.789-09 recusado").para_dict())
        self.assertEqual((dados["cliente"], dados["msg"], dados["pendencias"][0]["detalhe"]),
                         ("Fulano", "CPF ***8909 recusado", "***0001 → ***0001"))


class TestGerenciador(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "execucoes"
        self.gerenciador = GerenciadorTarefas(RegistroExecucoes(self.pasta))
        self.liberar = threading.Event()

    def tearDown(self):
        self.liberar.set()
        for thread in threading.enumerate():
            if thread.name.startswith("tarefa-"):
                thread.join(5)  # termina de gravar o registro antes de apagar a pasta
        self._tmp.cleanup()

    def _trabalho(self, tarefa):
        tarefa.passo_atualizado(0, _Passo("concluido", "E-book ativo"))
        tarefa.registrar("Contrato 2447: E-book ativo", NivelLog.SUCESSO)
        self.liberar.wait(5)
        return ResumoExecucao(1, 0, 0)

    def _tarefa(self):
        return Tarefa(contexto={"tipo": "lote"}, passos=[{}])

    def test_so_uma_execucao_por_vez_mesmo_com_pedidos_simultaneos(self):
        resultados = []

        def pedir():
            try:
                self.gerenciador.iniciar(self._tarefa(), self._trabalho, {})
                resultados.append("ok")
            except ErroEstado:
                resultados.append("recusado")

        threads = [threading.Thread(target=pedir) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(resultados), ["ok"] + ["recusado"] * 7)

    def test_registro_acompanha_a_execucao_e_fecha_no_fim(self):
        tarefa = self.gerenciador.iniciar(self._tarefa(), self._trabalho, {"provedor": "Meu provedor"})
        arquivo = Path(tarefa.arquivo)
        diario = arquivo.with_suffix(".diario.jsonl")
        _esperar(lambda: diario.exists() and len(diario.read_text(encoding="utf-8").splitlines()) >= 2)
        # ainda rodando: o retrato diz "rodando" e o diário já tem o contrato, com o telefone mascarado
        self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8"))["status"], "rodando")
        contrato = json.loads(diario.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((contrato["tipo"], contrato["contrato"], contrato["pendencias"][0]["detalhe"]),
                         ("contrato", "2447", "***0001 → ***0001"))

        self.liberar.set()
        _esperar(lambda: tarefa.status is not StatusTarefa.RODANDO)
        _esperar(lambda: json.loads(arquivo.read_text(encoding="utf-8"))["status"] == "concluido")
        self.assertNotIn("99999", arquivo.read_text(encoding="utf-8"))

    @unittest.skipIf(sys.platform == "win32", "permissões POSIX")
    def test_registro_so_o_dono_le(self):
        tarefa = self.gerenciador.iniciar(self._tarefa(), self._trabalho, {})
        self.liberar.set()
        _esperar(lambda: tarefa.status is not StatusTarefa.RODANDO)
        self.assertEqual(stat.S_IMODE(os.stat(self.pasta).st_mode), 0o700)
        for arquivo in self.pasta.iterdir():
            self.assertEqual(stat.S_IMODE(arquivo.stat().st_mode), 0o600, arquivo.name)

    def test_retencao_apaga_registros_antigos(self):
        registro = RegistroExecucoes(self.pasta, retencao_dias=90)
        self.pasta.mkdir(parents=True)
        velho, novo = self.pasta / "velho.json", self.pasta / "novo.diario.jsonl"
        for arquivo in (velho, novo):
            arquivo.write_text("{}", encoding="utf-8")
        cem_dias = time.time() - 100 * 86400
        os.utime(velho, (cem_dias, cem_dias))
        self.assertEqual(registro.limpar_antigos(), 1)
        self.assertEqual([p.name for p in self.pasta.iterdir()], ["novo.diario.jsonl"])

    def test_retencao_zero_guarda_tudo(self):
        self.assertEqual(RegistroExecucoes(self.pasta, retencao_dias=0).limpar_antigos(), 0)


if __name__ == "__main__":
    unittest.main()
