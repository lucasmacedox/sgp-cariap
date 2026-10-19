"""API local da interface. Rotas são métodos marcados com ``@rota`` que recebem e devolvem ``dict``."""

from __future__ import annotations

import inspect
from collections.abc import Callable

from ..ambiente import Ambiente
from ..cadastro import AssistenteCadastro
from ..dominio import Configuracao
from ..erros import ErroAssistente, ErroEstado
from .tarefas import GerenciadorTarefas, RegistroExecucoes, Tarefa

Manipulador = Callable[[dict], dict]
FabricaAssistente = Callable[..., AssistenteCadastro]

_ATRIBUTO_ROTA = "_rota_http"


def rota(metodo: str, caminho: str):
    def marcar(funcao):
        setattr(funcao, _ATRIBUTO_ROTA, (metodo.upper(), caminho))
        return funcao
    return marcar


class RotaInexistente(ErroAssistente):
    pass


class ApiAssistente:
    def __init__(self, ambiente: Ambiente, *, conectar: FabricaAssistente = AssistenteCadastro.conectar,
                 tarefas: GerenciadorTarefas | None = None):
        self._ambiente = ambiente
        self._conectar = conectar
        self._tarefas = tarefas or GerenciadorTarefas(RegistroExecucoes(ambiente.execucoes))
        self._assistente: AssistenteCadastro | None = None
        self._rotas: dict[tuple[str, str], Manipulador] = {
            getattr(funcao, _ATRIBUTO_ROTA): getattr(self, nome)
            for nome, funcao in inspect.getmembers(type(self), inspect.isfunction)
            if hasattr(funcao, _ATRIBUTO_ROTA)
        }

    def despachar(self, metodo: str, caminho: str, dados: dict) -> dict:
        manipulador = self._rotas.get((metodo.upper(), caminho))
        if manipulador is None:
            raise RotaInexistente(f"rota inexistente: {metodo} {caminho}")
        return manipulador(dados)

    @property
    def assistente(self) -> AssistenteCadastro:
        if self._assistente is None:
            raise ErroEstado("conecte ao SGP primeiro")
        return self._assistente

    @rota("POST", "/api/conectar")
    def conectar(self, dados: dict) -> dict:
        url, usuario, senha = (str(dados.get(c) or "").strip() for c in ("url", "usuario", "senha"))
        if not (url and usuario and senha):
            raise ErroAssistente("preencha endereço, usuário e senha")
        self._sem_execucao("conectar a outro SGP")
        self._assistente = self._conectar(url, usuario, senha, verificar_ssl=not dados.get("ignorar_ssl"))
        return self._estado_conexao()

    @rota("GET", "/api/status")
    def status(self, dados: dict) -> dict:
        base = {"versao": self._ambiente.versao, "dados": str(self._ambiente.dados)}
        if self._assistente is None:
            return {**base, "conectado": False}
        return {**base, **self._estado_conexao()}

    @rota("POST", "/api/desconectar")
    def desconectar(self, dados: dict) -> dict:
        self._sem_execucao("desconectar")
        self._assistente = None
        return {"conectado": False}

    def _sem_execucao(self, acao: str) -> None:
        if self._tarefas.em_andamento():
            raise ErroEstado(f"há uma execução em andamento; pare a execução antes de {acao}")

    def _estado_conexao(self) -> dict:
        return {"conectado": True, "url": self.assistente.url, "usuario": self.assistente.usuario,
                "versao_sgp": self.assistente.versao_sgp}

    @rota("GET", "/api/planos")
    def planos(self, dados: dict) -> dict:
        return self.assistente.planos(reler=bool(dados.get("reler")))

    @rota("GET", "/api/lote/opcoes")
    def lote_opcoes(self, dados: dict) -> dict:
        return self.assistente.opcoes_lote()

    @rota("POST", "/api/lote/montar")
    def lote_montar(self, dados: dict) -> dict:
        itens = self.assistente.montar_lote(Configuracao.de_dict(dados.get("config")))
        return {"itens": [i.para_dict() for i in itens]}

    @rota("POST", "/api/lote/iniciar")
    def lote_iniciar(self, dados: dict) -> dict:
        if self._tarefas.em_andamento():
            raise ErroEstado("já há uma execução em andamento")
        assistente = self.assistente
        config = Configuracao.de_dict(dados.get("config"))
        selecionados = {str(c) for c in dados.get("selecionados") or []}
        # remonta para não repetir contratos que já receberam os serviços desde a busca
        itens = assistente.montar_lote(config, selecionados)
        pendentes = sum(i.a_fazer for i in itens)
        if not pendentes:
            raise ErroAssistente("nenhum contrato pendente selecionado")
        tarefa = Tarefa(contexto={"tipo": "lote", "sgp": assistente.url, "usuario": assistente.usuario,
                                  "versao_sgp": assistente.versao_sgp,
                                  "pausa_segundos": config.lote.pausa_segundos or 0,
                                  "limite": config.lote.limite or 0},
                        passos=[i.para_dict() for i in itens])
        tarefa.registrar(f"Início · {pendentes} contrato(s) · {assistente.url}")
        self._tarefas.iniciar(tarefa, lambda t: assistente.aplicar_lote(config, itens, t, t.controle),
                              dados.get("config") or {})
        return {"job": tarefa.id}

    @rota("POST", "/api/job/controle")
    def tarefa_controle(self, dados: dict) -> dict:
        tarefa = self._tarefa(dados)
        acoes = {"pausar": tarefa.controle.pausar, "retomar": tarefa.controle.retomar, "parar": tarefa.controle.parar}
        if dados.get("acao") not in acoes:
            raise ErroAssistente("ação inválida")
        acoes[dados["acao"]]()
        tarefa.registrar({"pausar": "Pausado", "retomar": "Retomado",
                          "parar": "Parando após o contrato atual"}[dados["acao"]])
        return tarefa.para_dict()

    @rota("GET", "/api/job")
    def tarefa(self, dados: dict) -> dict:
        return self._tarefa(dados).para_dict()

    def _tarefa(self, dados: dict) -> Tarefa:
        tarefa = self._tarefas.obter(str(dados.get("id", "")))
        if tarefa is None:
            raise ErroAssistente("execução não encontrada")
        return tarefa
