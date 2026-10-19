"""Aplicação dos serviços nos contratos, um por vez, no contrato que já existe (mesma fatura).

``MontadorLote`` compara o que cada contrato tem com o que o mapeamento pede;
``ExecutorLote`` adiciona e ativa o que falta. Rodar de novo só faz o que ainda falta.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ..dominio import Configuracao, ConfiguracaoLote, nome_do_plano
from ..erros import ErroAssistente, ErroAtivacao
from ..sgp import FiltroServicos, NovoServicoTV
from .execucao import NivelLog, ObservadorExecucao, ResumoExecucao
from .falhas import Falha, classificar
from .validacao import NAO_ENCONTRADO, Pendencia, validar

if TYPE_CHECKING:
    from .catalogo import CatalogoSGP


class SituacaoItem(str, Enum):
    PENDENTE = "pendente"
    COMPLETO = "completo"
    RODANDO = "rodando"
    CONCLUIDO = "concluido"
    ERRO = "erro"
    PULADO = "pulado"
    BLOQUEADO = "bloqueado"  # pendência no cadastro do cliente


@dataclass
class ItemLote:
    contrato_id: str
    cliente: str
    plano_internet: str
    servico_internet_id: str
    servicos: list[str]
    faltando: list[str] = field(default_factory=list)
    inativos: dict[str, str] = field(default_factory=dict)  # serviço → ID do serviço de TV
    situacao: SituacaoItem = SituacaoItem.PENDENTE
    mensagem: str = ""
    etapa: str = ""
    falhas: list[Falha] = field(default_factory=list)
    duracao: float | None = None
    cliente_id: str = ""
    pendencias: list[Pendencia] = field(default_factory=list)

    @property
    def a_fazer(self) -> bool:
        return self.situacao is SituacaoItem.PENDENTE

    def para_dict(self) -> dict:
        return {"chave": self.contrato_id, "contrato": self.contrato_id, "cliente": self.cliente,
                "plano_internet": self.plano_internet, "servicos": self.servicos, "faltando": self.faltando,
                "ativar": sorted(self.inativos), "situacao": self.situacao.value, "msg": self.mensagem,
                "etapa": self.etapa, "falhas": [f.para_dict() for f in self.falhas],
                "causa": self.falhas[0].causa.value if self.falhas else "", "duracao": self.duracao,
                "cliente_id": self.cliente_id, "pendencias": [p.para_dict() for p in self.pendencias]}


class MontadorLote:
    def __init__(self, catalogo: CatalogoSGP, config: Configuracao):
        self._catalogo = catalogo
        self._relatorio = catalogo.telas.relatorio_servicos
        self._config = config
        self._lote: ConfiguracaoLote = config.lote

    def planos(self) -> list[str]:
        rotulos = self._lote.planos or self._config.planos_mapeados()
        return sorted({nome_do_plano(r) for r in rotulos})

    def montar(self) -> list[ItemLote]:
        problemas = self._config.problemas()
        if problemas:
            raise ErroAssistente("corrija os serviços antes: " + "; ".join(problemas))
        planos, servicos = self.planos(), self._config.servicos_usados()
        if not planos or not servicos:
            raise ErroAssistente("defina ao menos um grupo com planos e serviços")
        self._verificar_versao()
        self._verificar_planos_tv(servicos)
        desejados = self._config.servicos_por_plano()
        internet = self._relatorio.buscar(FiltroServicos(
            tipo="Internet", planos_internet=planos, pops=self._lote.pops,
            status_contrato=self._lote.status_contrato or ["Ativo"]))
        existentes = self._servicos_por_contrato(servicos)

        itens: dict[str, ItemLote] = {}
        for servico in internet:
            if servico.contrato_id in itens or servico.plano.lower() not in desejados:
                continue  # contrato com dois serviços de internet vira um item só
            item = ItemLote(servico.contrato_id, servico.cliente, servico.plano, servico.servico_id,
                            desejados[servico.plano.lower()])
            self._comparar(item, existentes.get(servico.contrato_id, {}))
            itens[item.contrato_id] = item
        self._conferir_cadastros([i for i in itens.values() if i.a_fazer])
        return sorted(itens.values(), key=lambda i: (not i.a_fazer, i.cliente))

    def _conferir_cadastros(self, itens: list[ItemLote]) -> None:
        if not itens or not self._lote.validar_cadastro:
            return
        exportacoes = []
        motivos: dict[str, str] = {}
        for plano in sorted({i.plano_internet for i in itens}):
            try:
                exportacoes.append(self._catalogo.telas.lista_clientes.contatos(
                    [plano], self._lote.pops, self._lote.status_contrato or ["Ativo"]))
            except ErroAssistente as erro:
                motivos[plano] = f"não deu para ler os contatos no SGP ({erro})"
        for item in itens:
            dados = next((e[item.contrato_id] for e in exportacoes if item.contrato_id in e), None)
            item.cliente_id = dados.cliente_id if dados else ""
            item.pendencias = validar(dados, motivos.get(item.plano_internet, NAO_ENCONTRADO))
            bloqueios = [p.titulo for p in item.pendencias if p.bloqueia]
            if bloqueios:
                item.situacao, item.mensagem = SituacaoItem.BLOQUEADO, ", ".join(bloqueios)

    def _verificar_versao(self) -> None:
        problemas = self._catalogo.telas.incompatibilidades(cadastro=self._lote.validar_cadastro)
        if problemas:
            versao = self._catalogo.cliente.versao_sgp
            raise ErroAssistente(f"este SGP{f' (versão {versao})' if versao else ''} tem telas diferentes das "
                                 f"conhecidas pelo assistente: {'; '.join(problemas)}. Envie esta mensagem ao suporte.")

    def _verificar_planos_tv(self, servicos: list[str]) -> None:
        # plano de TV sem POP não aparece no formulário de nenhum contrato
        ids = {p.nome.lower(): p.id for p in self._catalogo.planos_servico}
        sem_pop = [s for s in servicos if s.lower() in ids
                   and not self._catalogo.telas.lista_planos.pops(ids[s.lower()])]
        if sem_pop:
            raise ErroAssistente("sem POP no SGP: " + ", ".join(sem_pop)
                                 + ". Inclua os POPs no cadastro do plano e busque de novo.")

    def _servicos_por_contrato(self, servicos: list[str]) -> dict[str, dict[str, tuple[str, str]]]:
        por_contrato: dict[str, dict[str, tuple[str, str]]] = {}
        for tv in self._relatorio.buscar(FiltroServicos(tipo="TV", planos_tv=servicos)):
            do_contrato = por_contrato.setdefault(tv.contrato_id, {})
            atual = do_contrato.get(tv.plano.lower())
            if atual is None or tv.situacao == "Ativo":
                do_contrato[tv.plano.lower()] = (tv.servico_id, tv.situacao)
        return por_contrato

    def _comparar(self, item: ItemLote, existentes: dict[str, tuple[str, str]]) -> None:
        for servico in item.servicos:
            atual = existentes.get(servico.lower())
            if atual is None:
                item.faltando.append(servico)
            elif atual[1] != "Ativo" and self._lote.ativar:
                item.inativos[servico] = atual[0]
        partes = []
        if item.faltando:
            partes.append("faltam " + ", ".join(item.faltando))
        if item.inativos:
            partes.append("ativar " + ", ".join(item.inativos))
        if partes:
            item.mensagem = "; ".join(partes)
        else:
            item.situacao, item.mensagem = SituacaoItem.COMPLETO, "já tem todos os serviços"


@dataclass
class ControleExecucao:
    _liberado: threading.Event = field(default_factory=threading.Event)
    _parar: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self):
        self._liberado.set()

    @property
    def pausado(self) -> bool:
        return not self._liberado.is_set()

    @property
    def parada_pedida(self) -> bool:
        return self._parar.is_set()

    def pausar(self) -> None:
        self._liberado.clear()

    def retomar(self) -> None:
        self._liberado.set()

    def parar(self) -> None:
        self._parar.set()
        self._liberado.set()

    def esperar(self, segundos: float) -> bool:
        """``False`` se pediram para parar."""
        if self._parar.wait(timeout=max(0.0, segundos)):
            return False
        self._liberado.wait()
        return not self._parar.is_set()


class ExecutorLote:
    """A falha de um contrato não interrompe os demais, salvo falhas gerais seguidas."""

    LIMITE_FALHAS_GERAIS = 3

    def __init__(self, catalogo: CatalogoSGP, config: Configuracao,
                 observador: ObservadorExecucao, controle: ControleExecucao,
                 relogio: Callable[[], float] = time.monotonic):
        self._tela = catalogo.telas.servico_tv
        self._padroes = config.padroes
        self._lote = config.lote
        self._observador = observador
        self._controle = controle
        self._relogio = relogio

    def executar(self, itens: list[ItemLote]) -> ResumoExecucao:
        pendentes = [i for i, item in enumerate(itens) if item.a_fazer]
        if self._lote.limite:
            pendentes = pendentes[: self._lote.limite]
        gerais_seguidas = 0
        for posicao, indice in enumerate(pendentes):
            if posicao and not self._controle.esperar(self._lote.pausa_segundos or 0):
                self._observador.registrar("Parado. Os contratos restantes continuam pendentes.", NivelLog.ERRO)
                break
            if self._controle.parada_pedida:
                break
            item = itens[indice]
            self._processar(indice, item)
            so_gerais = bool(item.falhas) and all(f.geral for f in item.falhas)
            gerais_seguidas = gerais_seguidas + 1 if so_gerais else 0
            if gerais_seguidas >= self.LIMITE_FALHAS_GERAIS:
                causa = item.falhas[0].diagnostico
                self._observador.registrar(
                    f"Interrompido: {causa.titulo.lower()} em {gerais_seguidas} contratos seguidos. "
                    f"{causa.orientacao} Os restantes continuam pendentes.", NivelLog.ERRO)
                break
        total = Counter(i.situacao for i in itens)
        return ResumoExecucao(total[SituacaoItem.CONCLUIDO], total[SituacaoItem.ERRO])

    def _processar(self, indice: int, item: ItemLote) -> None:
        inicio = self._relogio()
        item.falhas = []
        self._mudar(indice, item, SituacaoItem.RODANDO, item.mensagem, etapa="Preparando")
        feitos: list[str] = []
        endereco = self._endereco(indice, item)
        if endereco is not None:
            feitos += self._adicionar_faltantes(indice, item, endereco)
        feitos += self._ativar_inativos(indice, item)
        item.duracao = round(self._relogio() - inicio, 1)
        rotulo = f"Contrato {item.contrato_id} ({item.cliente})"
        if item.falhas:
            mensagem = "; ".join(f"{f.servico}: {f.mensagem}" if f.servico else f.mensagem for f in item.falhas)
            self._mudar(indice, item, SituacaoItem.ERRO, mensagem)
            self._observador.registrar(f"{rotulo}: falhou ({mensagem})", NivelLog.ERRO)
        else:
            self._mudar(indice, item, SituacaoItem.CONCLUIDO, "; ".join(feitos))
            self._observador.registrar(f"{rotulo}: {', '.join(feitos)}", NivelLog.SUCESSO)

    def _endereco(self, indice: int, item: ItemLote) -> dict[str, str] | None:
        if not item.faltando:
            return {}
        self._etapa(indice, item, "Lendo endereço")
        try:
            return self._tela.endereco_de_instalacao(item.servico_internet_id)
        except Exception as erro:  # noqa: BLE001
            falha = classificar(erro)
            item.falhas.append(Falha("", falha.causa, f"endereço de instalação: {falha.mensagem}"))
            return None

    def _adicionar_faltantes(self, indice: int, item: ItemLote, endereco: dict[str, str]) -> list[str]:
        feitos = []
        total = len(item.faltando)
        for numero, servico in enumerate(list(item.faltando), start=1):
            self._etapa(indice, item, f"Adicionando {servico}" + (f" ({numero}/{total})" if total > 1 else ""))
            try:
                servico_id = self._tela.adicionar(item.contrato_id, NovoServicoTV(
                    grupo=self._padroes.grupo_tv or "TV", plano=servico, endereco=endereco,
                    modo_aquisicao=self._padroes.modo_aquisicao or "Comodato"))
            except Exception as erro:  # noqa: BLE001
                item.falhas.append(classificar(erro, servico))
                if item.falhas[-1].geral:
                    break
                continue
            item.faltando.remove(servico)
            if self._lote.ativar:
                item.inativos[servico] = servico_id
            else:
                feitos.append(f"{servico} adicionado")
        return feitos

    def _ativar_inativos(self, indice: int, item: ItemLote) -> list[str]:
        feitos: list[str] = []
        if item.falhas and item.falhas[-1].geral:
            return feitos
        for servico, servico_id in list(item.inativos.items()):
            self._etapa(indice, item, f"Ativando {servico}")
            try:
                if not self._tela.ativar(servico_id):
                    raise ErroAtivacao(f"não ativou. {self._ORIENTACAO}")
            except Exception as erro:  # noqa: BLE001
                item.falhas.append(classificar(erro, servico))
                if item.falhas[-1].geral:
                    break
                continue
            del item.inativos[servico]
            feitos.append(f"{servico} ativo")
        return feitos

    _ORIENTACAO = "Confira CPF, e-mail e celular do cliente e se o contrato está ativo"

    def _etapa(self, indice: int, item: ItemLote, texto: str) -> None:
        item.etapa = texto
        self._observador.passo_atualizado(indice, item)

    def _mudar(self, indice: int, item: ItemLote, situacao: SituacaoItem, mensagem: str = "", etapa: str = "") -> None:
        item.situacao, item.mensagem, item.etapa = situacao, mensagem, etapa
        self._observador.passo_atualizado(indice, item)
