"""Casos de uso do assistente para um SGP conectado (fachada da camada de aplicação)."""

from __future__ import annotations

from ..dominio import Configuracao
from ..sgp import ClienteSGP
from .catalogo import CatalogoSGP
from .execucao import ObservadorExecucao, ResumoExecucao
from .lote import ControleExecucao, ExecutorLote, ItemLote, MontadorLote, SituacaoItem


class AssistenteCadastro:
    """Conexão com um SGP: leitura dos planos e aplicação dos serviços nos clientes."""

    def __init__(self, catalogo: CatalogoSGP):
        self.catalogo = catalogo

    @classmethod
    def conectar(cls, url: str, usuario: str, senha: str, *, verificar_ssl: bool = True) -> AssistenteCadastro:
        return cls(CatalogoSGP(ClienteSGP.conectar(url, usuario, senha, verificar_ssl=verificar_ssl)))

    @property
    def url(self) -> str:
        return self.catalogo.cliente.url

    @property
    def usuario(self) -> str:
        return self.catalogo.cliente.usuario

    @property
    def versao_sgp(self) -> str:
        return getattr(self.catalogo.cliente, "versao_sgp", "")

    def planos(self, reler: bool = False) -> dict:
        if reler:
            self.catalogo.atualizar()
        return self.catalogo.resumo()

    def opcoes_lote(self) -> dict:
        return self.catalogo.telas.relatorio_servicos.opcoes_filtro()

    def montar_lote(self, config: Configuracao, selecionados: set[str] | None = None) -> list[ItemLote]:
        """Contratos dos planos mapeados; com ``selecionados``, os demais pendentes ficam de fora."""
        itens = MontadorLote(self.catalogo, config).montar()
        if selecionados is not None:
            for item in itens:
                if item.a_fazer and item.contrato_id not in selecionados:
                    item.situacao, item.mensagem = SituacaoItem.PULADO, "fora da seleção"
        return itens

    def aplicar_lote(self, config: Configuracao, itens: list[ItemLote], observador: ObservadorExecucao,
                     controle: ControleExecucao) -> ResumoExecucao:
        return ExecutorLote(self.catalogo, config, observador, controle).executar(itens)
