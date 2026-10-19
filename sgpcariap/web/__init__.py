"""Interface local: servidor HTTP, API e execuções em segundo plano."""

from .api import ApiAssistente, rota
from .servidor import ServidorAssistente
from .tarefas import GerenciadorTarefas, RegistroExecucoes, StatusTarefa, Tarefa

__all__ = ["ApiAssistente", "GerenciadorTarefas", "RegistroExecucoes", "ServidorAssistente",
           "StatusTarefa", "Tarefa", "rota"]
