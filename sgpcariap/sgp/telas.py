"""Telas do SGP usadas pelo assistente: rotas e nomes de campo ficam aqui.

No SGP, um GET em ``/ativar``, ``/desativar`` ou ``/delete/`` executa a ação sem
confirmação. Só ``ativar`` é usado.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from html import unescape
from urllib.parse import urlencode

from ..dominio.dinheiro import para_decimal
from ..erros import ErroIdentificacao, ErroPlanoIndisponivel, ErroSGP, OpcaoNaoEncontrada
from .cliente import ClienteSGP
from .formulario import Formulario, ListaOpcoes, ValorCampo
from .planilha import linhas_xlsx

_LINHA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELULA = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TAG = re.compile(r"<[^>]+>")


def linhas_de_tabela(html: str) -> list[tuple[str, list[str]]]:
    return [(linha, [" ".join(unescape(_TAG.sub(" ", c)).split()) for c in _CELULA.findall(linha)])
            for linha in _LINHA.findall(html)]


def _inteiro(texto: str) -> int:
    return int(texto) if texto.strip().isdigit() else 0


class Tela:
    """Tela de filtro; o formulário é lido uma vez."""

    rota = ""
    CAMPOS: tuple[str, ...] = ()  # se faltar algum, o SGP é de outra versão

    def __init__(self, cliente: ClienteSGP):
        self._cliente = cliente
        self._formulario: Formulario | None = None

    def formulario(self) -> Formulario:
        if self._formulario is None:
            self._formulario = self._cliente.formulario(self.rota)
        return self._formulario

    def opcoes(self, campo: str) -> ListaOpcoes:
        return self.formulario().opcoes_de(campo)

    def campos_ausentes(self) -> list[str]:
        return [campo for campo in self.CAMPOS if not self.formulario().tem_campo(campo)]


@dataclass(frozen=True)
class PlanoListado:
    id: str
    nome: str
    grupo: str
    preco: Decimal | None
    ativos: int = 0
    gateway: str = ""


class TelaListaPlanos:
    _ID = re.compile(r"/admin/plano/(\d+)/edit/")

    def __init__(self, cliente: ClienteSGP):
        self._cliente = cliente

    def _listar(self, rota: str) -> list[tuple[str, dict[str, str]]]:
        cabecalho: list[str] = []
        planos = []
        for linha, celulas in linhas_de_tabela(self._cliente.pagina(rota)):
            identificador = self._ID.search(linha)
            if not identificador:
                if "Descrição" in celulas:
                    cabecalho = celulas
                continue
            colunas: dict[str, str] = {}
            for titulo, valor in zip(cabecalho, celulas):
                colunas.setdefault(titulo, valor)  # a listagem repete "Total" (clientes e valor)
            planos.append((identificador.group(1), colunas))
        return planos

    def _planos(self, tipo: str) -> list[PlanoListado]:
        return [PlanoListado(id=i, nome=c.get("Descrição", ""), grupo=c.get("Grupo", ""),
                             preco=para_decimal(c.get("Preço")), ativos=_inteiro(c.get("Ativo") or c.get("Ativos", "")),
                             gateway=c.get("Gateway", ""))
                for i, c in self._listar(f"/admin/plano/{tipo}/")]

    def internet(self) -> list[PlanoListado]:
        return self._planos("internet")

    def tv(self) -> list[PlanoListado]:
        return self._planos("tv")

    def pops(self, plano_id: str) -> list[str]:
        return self._cliente.formulario(f"/admin/plano/{plano_id}/edit/").valores_de("form1-pops")


@dataclass(frozen=True)
class ServicoContratado:
    servico_id: str
    contrato_id: str
    cliente: str
    plano: str
    situacao: str


@dataclass(kw_only=True)
class FiltroServicos:
    tipo: str = "Internet"
    planos_internet: list[str] = field(default_factory=list)
    planos_tv: list[str] = field(default_factory=list)
    pops: list[str] = field(default_factory=list)
    status_contrato: list[str] = field(default_factory=list)


def _nome_plano(rotulo: str) -> str:
    return rotulo.split(" - ")[0].strip()


def ids_plano(opcoes: ListaOpcoes, nome: str) -> list[str]:
    """IDs de todos os planos com esse nome; as opções vêm como "Nome - Pós Pago - Download: ..."."""
    alvo = " ".join(nome.split()).lower()
    iguais = [o.valor for o in opcoes if o.valor and " ".join(_nome_plano(o.rotulo).split()).lower() == alvo]
    return iguais or [opcoes.resolver(f"{nome} - ", nome)]


class TelaRelatorioServicos(Tela):
    """Relatórios → Contratos → Serviços: a única consulta em massa de contratos."""

    rota = "/admin/relatorios/contrato/servico/"
    CAMPOS = ("tipo_servico", "planos_internet", "planos_tv", "pops", "contrato_status")
    _POR_PAGINA = "1000"
    _LIMITE_PAGINAS = 200
    _SERVICO = re.compile(r"/admin/servicos/(?:internet|tv|telefonia|multimidia|generico)/(\d+)/")

    def opcoes_filtro(self) -> dict[str, list[str]]:
        nomes = lambda campo: list(dict.fromkeys(_nome_plano(r) for r in self.opcoes(campo).rotulos()))  # noqa: E731
        return {
            "planos_internet": nomes("planos_internet"),
            "planos_tv": nomes("planos_tv"),
            "pops": self.opcoes("pops").rotulos(),
            "status": self.opcoes("contrato_status").rotulos(),
        }

    def _planos(self, campo: str, nomes: list[str]) -> list[str]:
        return list(dict.fromkeys(v for nome in nomes for v in ids_plano(self.opcoes(campo), nome)))

    def buscar(self, filtro: FiltroServicos) -> list[ServicoContratado]:
        formulario = self.formulario()
        resolver = lambda campo, textos: list(dict.fromkeys(  # noqa: E731
            v for t in textos for v in formulario.opcoes_de(campo).resolver_todos(t, t)))
        alteracoes: dict[str, ValorCampo] = {
            "tipo_servico": formulario.opcoes_de("tipo_servico").resolver(filtro.tipo, "tipo de serviço"),
            "planos_internet": self._planos("planos_internet", filtro.planos_internet),
            "planos_tv": self._planos("planos_tv", filtro.planos_tv),
            "pops": resolver("pops", filtro.pops),
            "contrato_status": resolver("contrato_status", filtro.status_contrato),
            "paginate_by": self._POR_PAGINA,
        }
        resultado: list[ServicoContratado] = []
        vistos: set[str] = set()
        for pagina in range(1, self._LIMITE_PAGINAS + 1):
            consulta = formulario.preencher({**alteracoes, "page": str(pagina)})
            html = self._cliente.pagina(f"{self.rota}?{urlencode(consulta)}")
            novos = [s for s in self._ler(html) if s.servico_id not in vistos]
            if not novos:
                break
            vistos.update(s.servico_id for s in novos)
            resultado.extend(novos)
            if len(novos) < int(self._POR_PAGINA):
                break
        return resultado

    def _ler(self, html: str) -> list[ServicoContratado]:
        servicos = []
        for linha, celulas in linhas_de_tabela(html):
            achado = self._SERVICO.search(linha)
            if not achado or len(celulas) < 9:
                continue
            contrato, _, cliente = celulas[2].partition(" - ")
            servicos.append(ServicoContratado(achado.group(1), contrato.strip(), cliente.strip(), celulas[3], celulas[8]))
        return servicos


@dataclass(frozen=True)
class ContatosCliente:
    cliente_id: str
    documento: str
    celulares: tuple[str, ...] = ()
    telefones: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()

    def juntar(self, outro: ContatosCliente) -> ContatosCliente:
        unir = lambda a, b: tuple(dict.fromkeys(a + b))  # noqa: E731
        return ContatosCliente(self.cliente_id or outro.cliente_id, self.documento or outro.documento,
                               unir(self.celulares, outro.celulares), unir(self.telefones, outro.telefones),
                               unir(self.emails, outro.emails))


class TelaListaClientes(Tela):
    """Contatos pela exportação Excel da lista de clientes, uma por plano para não estourar o tempo.

    A planilha traz a senha do PPPoE; só as colunas de ``_COLUNAS`` são lidas.
    """

    rota = "/admin/cliente/list/"
    CAMPOS = ("planointernet", "popservico")
    _TEMPO_LIMITE = 300
    _CLIENTE = re.compile(r"/admin/cliente/\d+/")
    _COLUNAS = {"cliente_id": "Cliente ID", "contrato_id": "Contrato ID", "documento": "CPF/CNPJ",
                "celulares": "Celulares", "telefones": "Telefones", "emails": "Emails"}

    def contatos(self, planos_internet: Sequence[str], pops: Sequence[str] = (),
                 status_contrato: Sequence[str] = ()) -> dict[str, ContatosCliente]:
        opcoes = self.opcoes
        filtros = [("popservico", v) for p in pops for v in opcoes("popservico").resolver_todos(p, "POP")]
        for status in status_contrato:
            try:
                filtros += [("status", v) for v in opcoes("status").resolver_todos(status, "status")]
            except OpcaoNaoEncontrada:
                pass
        resultado: dict[str, ContatosCliente] = {}
        ids = dict.fromkeys(v for plano in planos_internet for v in ids_plano(opcoes("planointernet"), plano))
        for plano_id in ids:
            consulta = [("tipoq", "cliente"), ("planointernet", plano_id), *filtros, ("printexcel", "true")]
            resposta = self._cliente.arquivo(f"{self.rota}?{urlencode(consulta)}", timeout=self._TEMPO_LIMITE)
            if "html" in (resposta.cabecalhos.get("Content-Type") or ""):
                # filtro sem clientes: o SGP devolve a página da lista em vez da planilha
                if self._CLIENTE.search(resposta.texto):
                    raise ErroSGP("este SGP mostrou a lista de clientes em vez de exportar o Excel")
                continue
            for contrato, contatos in self._ler(resposta.conteudo).items():
                resultado[contrato] = resultado[contrato].juntar(contatos) if contrato in resultado else contatos
        return resultado

    @classmethod
    def _ler(cls, dados: bytes) -> dict[str, ContatosCliente]:
        linhas = linhas_xlsx(dados)
        cabecalho = next((i for i, lin in enumerate(linhas) if lin and lin[0].strip() == cls._COLUNAS["cliente_id"]), None)
        if cabecalho is None:
            raise ErroSGP("a exportação de clientes do SGP veio sem cabeçalho reconhecível")
        nomes = [c.strip() for c in linhas[cabecalho]]
        faltam = [n for n in cls._COLUNAS.values() if n not in nomes]
        if faltam:
            raise ErroSGP("a exportação de clientes do SGP não tem as colunas " + ", ".join(faltam))
        coluna = {chave: nomes.index(nome) for chave, nome in cls._COLUNAS.items()}
        resultado: dict[str, ContatosCliente] = {}
        for linha in linhas[cabecalho + 1:]:
            def valor(chave: str, linha: list[str] = linha) -> str:
                return linha[coluna[chave]].strip() if coluna[chave] < len(linha) else ""
            contrato = valor("contrato_id")
            if not contrato:
                continue
            contatos = ContatosCliente(valor("cliente_id"), valor("documento"), _contatos(valor("celulares")),
                                       _contatos(valor("telefones")), _contatos(valor("emails")))
            resultado[contrato] = resultado[contrato].juntar(contatos) if contrato in resultado else contatos
        return resultado


def _contatos(celula: str) -> tuple[str, ...]:
    """"Celular Pessoal: (84) 99999-0001" → "(84) 99999-0001", um por linha."""
    contatos = []
    for linha in celula.splitlines():
        tipo, separador, valor = linha.partition(": ")
        if separador and "@" not in tipo and not any(c.isdigit() for c in tipo):
            linha = valor
        if linha.strip():
            contatos.append(linha.strip())
    return tuple(contatos)


_ENDERECO = ("cep", "logradouro", "numero", "bairro", "cidade", "uf", "complemento", "pontoreferencia")


@dataclass(kw_only=True)
class NovoServicoTV:
    grupo: str
    plano: str
    endereco: dict[str, str]
    modo_aquisicao: str = "Comodato"


class TelaServicoTV:
    _CLIENTE = re.compile(r"/admin/cliente/(\d+)/")
    _SERVICO_TV = re.compile(r"/admin/servicos/tv/(\d+)/")

    def __init__(self, cliente: ClienteSGP):
        self._cliente = cliente
        self._tv_por_cliente: dict[str, set[str]] = {}

    def endereco_de_instalacao(self, servico_internet_id: str) -> dict[str, str]:
        formulario = self._cliente.formulario(f"/admin/servicos/internet/{servico_internet_id}/")
        return {campo: (formulario.valores_de(f"enderecoinst-{campo}") or [""])[0] for campo in _ENDERECO}

    def _servicos_tv_do_cliente(self, cliente_id: str) -> set[str]:
        servicos = set(self._SERVICO_TV.findall(self._cliente.pagina(f"/admin/cliente/{cliente_id}/contratos/")))
        self._tv_por_cliente[cliente_id] = servicos
        return servicos

    def adicionar(self, contrato_id: str, novo: NovoServicoTV) -> str:
        """Grava o serviço e devolve o ID, achado pela diferença nos serviços do cliente."""
        rota = f"/admin/clientecontrato/{contrato_id}/tv/add/"
        html = self._cliente.pagina(rota)
        formulario = Formulario.de_html(html)
        achado = self._CLIENTE.search(html)
        cliente_id = achado.group(1) if achado else ""
        antes = set(self._tv_por_cliente.get(cliente_id) or (self._servicos_tv_do_cliente(cliente_id) if cliente_id else ()))
        opcoes = formulario.opcoes_de
        campos: dict[str, ValorCampo] = {
            "servicot-grupo": opcoes("servicot-grupo").resolver(novo.grupo, "grupo"),
            "servicot-plano": self._plano(formulario, novo.plano),
            "servicot-modoaquisicao": opcoes("servicot-modoaquisicao").resolver(novo.modo_aquisicao, "modo de aquisição"),
            "servicot-os_instalacao": None,
        }
        campos.update({f"enderecoinst-{k}": v for k, v in novo.endereco.items()})
        destino = self._cliente.enviar(rota, campos, formulario=formulario)
        cliente_id = cliente_id or (self._CLIENTE.search(destino) or [None, ""])[1]
        novos = self._servicos_tv_do_cliente(cliente_id) - antes if cliente_id else set()
        if len(novos) != 1:
            raise ErroIdentificacao("serviço gravado, mas não identificado para ativar. Ative pelo SGP")
        return novos.pop()

    @staticmethod
    def _plano(formulario: Formulario, plano: str) -> str:
        try:
            return formulario.opcoes_de("servicot-plano").resolver(f"{plano} - ", plano)
        except OpcaoNaoEncontrada:
            # o SGP só lista os planos liberados para o POP do contrato
            raise ErroPlanoIndisponivel("plano indisponível no POP deste contrato. Inclua o POP no cadastro do plano") from None

    def ativar(self, servico_id: str) -> bool:
        """Ativa e diz se o serviço ficou ativo (a página só oferece "desativar" para serviço ativo)."""
        servico = f"/admin/servicos/tv/{servico_id}/"
        html, endereco = self._cliente.pagina_e_endereco(f"{servico}ativar")
        if servico not in endereco:
            html = self._cliente.pagina(servico)
        return f"{servico}desativar" in html


@dataclass
class TelasSGP:
    cliente: ClienteSGP

    def __post_init__(self):
        self.lista_planos = TelaListaPlanos(self.cliente)
        self.relatorio_servicos = TelaRelatorioServicos(self.cliente)
        self.lista_clientes = TelaListaClientes(self.cliente)
        self.servico_tv = TelaServicoTV(self.cliente)

    def incompatibilidades(self, *, cadastro: bool = True) -> list[str]:
        telas: list[tuple[str, Tela]] = [("Relatórios → Contratos → Serviços", self.relatorio_servicos)]
        if cadastro:
            telas.append(("Clientes → Lista", self.lista_clientes))
        problemas = []
        for nome, tela in telas:
            ausentes = tela.campos_ausentes()
            if ausentes:
                problemas.append(f"{nome} sem os campos {', '.join(ausentes)}")
        return problemas
