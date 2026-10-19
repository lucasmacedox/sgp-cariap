"""Leitura dos planos cadastrados no SGP do provedor."""

from __future__ import annotations

from functools import cached_property

from ..sgp import ClienteSGP, PlanoListado, TelasSGP


class CatalogoSGP:
    """Planos de internet e planos de serviço (grupo TV) lidos do SGP, com cache.

    ``atualizar`` descarta o cache; a próxima consulta relê o SGP.
    """

    _LEITURAS = ("planos_internet", "planos_servico")

    def __init__(self, cliente: ClienteSGP):
        self.cliente = cliente
        self.telas = TelasSGP(cliente)

    def atualizar(self) -> None:
        for nome in self._LEITURAS:
            self.__dict__.pop(nome, None)

    @cached_property
    def planos_internet(self) -> list[PlanoListado]:
        return self.telas.lista_planos.internet()

    @cached_property
    def planos_servico(self) -> list[PlanoListado]:
        """Planos do grupo TV: é onde o SGP cadastra os serviços do Cariap."""
        return self.telas.lista_planos.tv()

    def resumo(self) -> dict:
        return {
            "planos_internet": [_plano_para_dict(p) for p in self.planos_internet],
            "planos_servico": [_plano_para_dict(p) for p in self.planos_servico],
        }


def _plano_para_dict(plano: PlanoListado) -> dict:
    return {"id": plano.id, "rotulo": f"{plano.grupo} - {plano.nome}", "nome": plano.nome, "grupo": plano.grupo,
            "preco": float(plano.preco) if plano.preco is not None else None,
            "ativos": plano.ativos, "total": plano.total, "gateway": plano.gateway}
