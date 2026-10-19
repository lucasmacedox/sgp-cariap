"""Execuções em segundo plano: uma por vez e registro em disco."""

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sgpcariap.cadastro import NivelLog, ResumoExecucao
from sgpcariap.erros import ErroEstado
from sgpcariap.web.tarefas import GerenciadorTarefas, RegistroExecucoes, StatusTarefa, Tarefa


class _Passo:
    def __init__(self, situacao, msg=""):
        self.situacao, self.msg = situacao, msg

    def para_dict(self):
        return {"contrato": "2447", "cliente": "Fulano", "situacao": self.situacao, "msg": self.msg}


def _esperar(condicao, limite=5.0):
    fim = time.monotonic() + limite
    while not condicao():
        if time.monotonic() > fim:
            raise AssertionError("tempo esgotado")
        time.sleep(0.01)


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
                thread.join(5)
        self._tmp.cleanup()

    def _trabalho(self, tarefa):
        tarefa.passo_atualizado(0, _Passo("concluido", "E-book ativo"))
        tarefa.registrar("Contrato 2447: E-book ativo", NivelLog.SUCESSO)
        self.liberar.wait(5)
        return ResumoExecucao(1, 0)

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
        self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8"))["status"], "rodando")
        contrato = json.loads(diario.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((contrato["tipo"], contrato["contrato"]), ("contrato", "2447"))

        self.liberar.set()
        _esperar(lambda: tarefa.status is not StatusTarefa.RODANDO)
        _esperar(lambda: json.loads(arquivo.read_text(encoding="utf-8"))["status"] == "concluido")



if __name__ == "__main__":
    unittest.main()
