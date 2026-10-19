"""Execuções em segundo plano, acompanhadas pela interface via consulta periódica."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from collections.abc import Callable

from ..cadastro import ControleExecucao, NivelLog, ResumoExecucao
from ..erros import ErroEstado
from .privacidade import anonimizar

log = logging.getLogger(__name__)

_SITUACOES_FINAIS = {"concluido", "erro"}
_TAREFAS_EM_MEMORIA = 20


class StatusTarefa(str, Enum):
    RODANDO = "rodando"
    CONCLUIDA = "concluido"
    CONCLUIDA_COM_ERROS = "concluido_com_erros"
    FALHOU = "falhou"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Tarefa:
    """Estado de uma execução. Implementa ``ObservadorExecucao``.

    É escrita pela thread de execução e lida pelas requisições da interface;
    o lock garante leituras consistentes. ``diario`` recebe cada mensagem e cada
    contrato terminado, para o registro em disco acompanhar a execução.
    """

    contexto: dict
    passos: list[dict]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: StatusTarefa = StatusTarefa.RODANDO
    inicio: str = field(default_factory=_agora)
    fim: str | None = None
    arquivo: str | None = None
    log: list[dict] = field(default_factory=list)
    controle: ControleExecucao = field(default_factory=ControleExecucao, repr=False)
    diario: Callable[[dict], None] | None = field(default=None, repr=False)
    _trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def passo_atualizado(self, indice: int, passo) -> None:
        """``passo`` é qualquer objeto com ``para_dict`` (passo de cadastro ou item de lote)."""
        dados = passo.para_dict()
        with self._trava:
            self.passos[indice] = dados
        if dados.get("situacao") in _SITUACOES_FINAIS:
            self._anotar({"tipo": "contrato", **dados})

    def registrar(self, mensagem: str, nivel: NivelLog = NivelLog.INFO) -> None:
        entrada = {"t": datetime.now().strftime("%H:%M:%S"), "nivel": nivel.value, "msg": mensagem}
        with self._trava:
            self.log.append(entrada)
        self._anotar({"tipo": "log", **entrada})

    def concluir(self, resumo: ResumoExecucao) -> None:
        if resumo.sucesso:
            self.registrar("Concluído sem erros", NivelLog.SUCESSO)
        else:
            self.registrar(f"Concluído com {resumo.erros} erro(s)", NivelLog.ERRO)
        self._encerrar(StatusTarefa.CONCLUIDA if resumo.sucesso else StatusTarefa.CONCLUIDA_COM_ERROS)

    def falhar(self, erro: Exception) -> None:
        self.registrar(f"Interrompido: {erro}", NivelLog.ERRO)
        self._encerrar(StatusTarefa.FALHOU)

    def _encerrar(self, status: StatusTarefa) -> None:
        with self._trava:
            self.status, self.fim = status, _agora()

    def _anotar(self, evento: dict) -> None:
        if self.diario is not None:
            self.diario({"em": _agora(), **evento})

    def para_dict(self) -> dict:
        with self._trava:
            return {"id": self.id, "status": self.status.value, "inicio": self.inicio, "fim": self.fim,
                    "arquivo": self.arquivo, "passos": list(self.passos), "log": list(self.log),
                    "pausado": self.controle.pausado, "parada_pedida": self.controle.parada_pedida,
                    **self.contexto}


class RegistroExecucoes:
    """Registro de cada execução em disco: o que foi pedido e o que aconteceu.

    Por execução, dois arquivos com o mesmo nome:

    - ``.json``: o retrato completo; gravado no início (situação "rodando") e no fim;
    - ``.diario.jsonl``: uma linha por contrato terminado e por mensagem, gravada na
      hora. Se o assistente for fechado no meio, é ele que mostra o que já foi feito.

    Os arquivos só podem ser lidos pelo usuário que roda o assistente, os dados de
    contato do cliente vão mascarados (ver ``privacidade``) e registros mais antigos
    que ``retencao_dias`` são apagados ao iniciar uma nova execução (0 guarda todos).
    """

    def __init__(self, diretorio: Path, retencao_dias: int = 0):
        self.diretorio = diretorio
        self.retencao_dias = retencao_dias
        self._trava = threading.Lock()

    def abrir(self, tarefa: Tarefa, configuracao: dict) -> Path:
        """Cria o registro da execução e liga o diário à tarefa."""
        self._preparar_pasta()
        self.limpar_antigos()
        provedor = "".join(c if c.isalnum() else "-" for c in configuracao.get("provedor") or "sgp")[:40]
        arquivo = self.diretorio / f"{datetime.now():%Y-%m-%d_%H%M%S}_{provedor}_{tarefa.id}.json"
        tarefa.arquivo = str(arquivo)
        diario = arquivo.with_suffix(".diario.jsonl")
        tarefa.diario = lambda evento: self._anexar(diario, evento)
        self.salvar(tarefa, configuracao)
        return arquivo

    def salvar(self, tarefa: Tarefa, configuracao: dict) -> Path:
        arquivo = Path(tarefa.arquivo) if tarefa.arquivo else self.abrir(tarefa, configuracao)
        conteudo = anonimizar({**tarefa.para_dict(), "config": configuracao})
        temporario = arquivo.with_suffix(".json.tmp")
        _gravar(temporario, json.dumps(conteudo, ensure_ascii=False, indent=2), "w")
        os.replace(temporario, arquivo)  # quem lê nunca vê o arquivo pela metade
        return arquivo

    def limpar_antigos(self, agora: float | None = None) -> int:
        if not self.retencao_dias or not self.diretorio.is_dir():
            return 0
        limite = (agora or time.time()) - self.retencao_dias * 86400
        apagados = 0
        for arquivo in self.diretorio.iterdir():
            if arquivo.suffix in (".json", ".jsonl") and arquivo.is_file() and arquivo.stat().st_mtime < limite:
                arquivo.unlink(missing_ok=True)
                apagados += 1
        return apagados

    def _preparar_pasta(self) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.diretorio, 0o700)
        except OSError:  # pasta de outro usuário ou sistema de arquivos sem permissões
            pass

    def _anexar(self, diario: Path, evento: dict) -> None:
        linha = json.dumps(anonimizar(evento), ensure_ascii=False) + "\n"
        try:
            with self._trava:
                _gravar(diario, linha, "a")
        except OSError as erro:  # o registro não pode derrubar a execução
            log.warning("diário não gravado em %s: %s", diario, erro)


def _gravar(caminho: Path, texto: str, modo: str) -> None:
    """Grava ``texto`` com permissão só para o dono do arquivo (0600)."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if modo == "a" else os.O_TRUNC)
    with open(os.open(caminho, flags, 0o600), modo, encoding="utf-8") as arquivo:
        arquivo.write(texto)


class GerenciadorTarefas:
    """Cria e acompanha tarefas; permite apenas uma execução por vez."""

    def __init__(self, registro: RegistroExecucoes):
        self._registro = registro
        self._tarefas: dict[str, Tarefa] = {}
        self._trava = threading.Lock()

    def em_andamento(self) -> bool:
        with self._trava:
            return self._rodando()

    def _rodando(self) -> bool:
        return any(t.status is StatusTarefa.RODANDO for t in self._tarefas.values())

    def obter(self, identificador: str) -> Tarefa | None:
        with self._trava:
            return self._tarefas.get(identificador)

    def iniciar(self, tarefa: Tarefa, trabalho: Callable[[Tarefa], ResumoExecucao],
                configuracao: dict) -> Tarefa:
        """Roda ``trabalho`` numa thread e salva o registro ao terminar.

        A verificação "já há execução" e o cadastro da nova tarefa acontecem sob a
        mesma trava: dois pedidos simultâneos (duplo clique, duas abas) não geram
        duas execuções sobre os mesmos contratos.
        """
        with self._trava:
            if self._rodando():
                raise ErroEstado("já há uma execução em andamento")
            self._esquecer_antigas()
            self._tarefas[tarefa.id] = tarefa
        try:
            self._registro.abrir(tarefa, configuracao)
        except OSError as erro:
            tarefa.registrar(f"Registro não pôde ser criado: {erro}", NivelLog.ERRO)
        threading.Thread(target=self._rodar, args=(tarefa, trabalho, configuracao),
                         name=f"tarefa-{tarefa.id}", daemon=True).start()
        return tarefa

    def _esquecer_antigas(self) -> None:
        terminadas = [i for i, t in self._tarefas.items() if t.status is not StatusTarefa.RODANDO]
        for identificador in terminadas[:max(0, len(terminadas) - _TAREFAS_EM_MEMORIA + 1)]:
            del self._tarefas[identificador]

    def _rodar(self, tarefa: Tarefa, trabalho: Callable[[Tarefa], ResumoExecucao], configuracao: dict) -> None:
        try:
            tarefa.concluir(trabalho(tarefa))
        except Exception as erro:  # noqa: BLE001 - a falha vai para o log da tarefa
            log.exception("execução %s interrompida", tarefa.id)
            tarefa.falhar(erro)
        try:
            self._registro.salvar(tarefa, configuracao)
        except OSError as erro:
            tarefa.registrar(f"Registro não salvo: {erro}", NivelLog.ERRO)
