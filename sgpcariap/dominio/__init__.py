"""Mapeamento de planos de internet para serviços."""

from .dinheiro import para_decimal
from .modelos import Configuracao, ConfiguracaoLote, nome_do_plano

__all__ = ["Configuracao", "ConfiguracaoLote", "nome_do_plano", "para_decimal"]
