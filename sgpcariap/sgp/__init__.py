"""Integração com a interface web do SGP."""

from .cliente import ClienteSGP
from .formulario import Formulario, ListaOpcoes, Opcao
from .telas import ContatosCliente, FiltroServicos, NovoServicoTV, PlanoListado, ServicoContratado, TelasSGP

__all__ = ["ClienteSGP", "ContatosCliente", "FiltroServicos", "Formulario", "ListaOpcoes", "NovoServicoTV", "Opcao",
           "PlanoListado", "ServicoContratado", "TelasSGP"]
