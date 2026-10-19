"""Integração com a interface web do SGP (leitura de planos e serviços dos clientes)."""

from .cliente import ClienteSGP
from .formulario import Formulario, ListaOpcoes, Opcao
from .telas import (ContatosCliente, FiltroServicos, NovoServicoTV, PlanoListado, ServicoContratado, SituacaoServicoTV,
                    TelaListaClientes, TelaListaPlanos, TelaRelatorioServicos, TelaServicoTV, TelasSGP)

__all__ = [
    "ClienteSGP", "ContatosCliente", "FiltroServicos", "Formulario", "ListaOpcoes", "NovoServicoTV", "Opcao",
    "PlanoListado", "ServicoContratado", "SituacaoServicoTV", "TelaListaClientes", "TelaListaPlanos",
    "TelaRelatorioServicos", "TelaServicoTV", "TelasSGP",
]
