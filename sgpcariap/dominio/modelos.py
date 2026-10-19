"""Modelos da configuração de um provedor.

O assistente não cadastra planos: eles já existem no SGP. A configuração diz
quais serviços (planos do grupo TV, como os livros do Cariap) os clientes de
cada plano de internet devem ter, e como aplicar isso nos contratos.

Planos de internet com os mesmos serviços ficam num ``GrupoServicos``; um plano
pertence a no máximo um grupo. Os planos são guardados como aparecem no SGP
("Fibra - 400_MEGA_FIBRA") e os serviços pelo nome do plano de TV.
"""

from __future__ import annotations

from dataclasses import dataclass

from .serializacao import Modelo, booleano, campo, inteiro, lista_de, lista_de_texto, texto


def nome_do_plano(rotulo: str) -> str:
    """"Fibra - 400_MEGA_FIBRA" → "400_MEGA_FIBRA" (o relatório de clientes mostra só o nome)."""
    grupo, separador, nome = rotulo.partition(" - ")
    return nome if separador else grupo


@dataclass
class Padroes(Modelo):
    grupo_tv: str = campo(padrao="TV")
    """Grupo de plano dos serviços (no SGP, o Cariap entra como gateway de TV)."""
    modo_aquisicao: str = campo(padrao="Comodato")


@dataclass
class GrupoServicos(Modelo):
    """Planos de internet cujos clientes recebem os mesmos serviços."""

    nome: str = campo()
    planos: list[str] = campo(conversor=lista_de_texto)
    servicos: list[str] = campo(conversor=lista_de_texto)


@dataclass
class ConfiguracaoLote(Modelo):
    """Quais contratos entram e como a aplicação se comporta."""

    planos: list[str] = campo(conversor=lista_de_texto)
    """Restringe a alguns planos mapeados; vazio usa todos os planos dos grupos."""
    pops: list[str] = campo(conversor=lista_de_texto)
    status_contrato: list[str] = campo(conversor=lista_de_texto, fabrica=lambda: ["Ativo"])
    ativar: bool = campo(conversor=booleano, padrao=True)
    validar_cadastro: bool = campo(conversor=booleano, padrao=True)
    """Confere e-mail, telefone e CPF/CNPJ antes; quem tiver pendência fica de fora."""
    pausa_segundos: int | None = campo(conversor=inteiro, padrao=2)
    limite: int | None = campo(conversor=inteiro, padrao=None)
    """Quantos contratos processar nesta execução (piloto). Vazio processa todos."""


@dataclass
class Configuracao(Modelo):
    provedor: str = campo()
    padroes: Padroes = campo(conversor=Padroes.de_dict, fabrica=Padroes)
    grupos: list[GrupoServicos] = campo(conversor=lista_de(GrupoServicos))
    lote: ConfiguracaoLote = campo(conversor=ConfiguracaoLote.de_dict, fabrica=ConfiguracaoLote)

    def servicos_por_plano(self) -> dict[str, list[str]]:
        """Nome do plano de internet (minúsculo) → serviços que os clientes dele devem ter."""
        mapa: dict[str, list[str]] = {}
        for grupo in self.grupos:
            for rotulo in grupo.planos:
                mapa[nome_do_plano(rotulo).lower()] = list(grupo.servicos)
        return mapa

    def planos_mapeados(self) -> list[str]:
        return [rotulo for grupo in self.grupos if grupo.servicos for rotulo in grupo.planos]

    def servicos_usados(self) -> list[str]:
        return sorted({s for grupo in self.grupos for s in grupo.servicos})

    def problemas(self) -> list[str]:
        """Inconsistências do mapeamento que impedem aplicar nos clientes."""
        problemas: list[str] = []
        dono: dict[str, str] = {}
        for grupo in self.grupos:
            rotulo = grupo.nome or "grupo sem nome"
            if not grupo.planos:
                problemas.append(f"{rotulo}: nenhum plano de internet")
            if not grupo.servicos:
                problemas.append(f"{rotulo}: nenhum serviço definido")
            for plano in grupo.planos:
                chave = texto(plano).lower()
                if chave in dono and dono[chave] != rotulo:
                    problemas.append(f'o plano "{plano}" está em dois grupos: {dono[chave]} e {rotulo}')
                dono.setdefault(chave, rotulo)
        return problemas
