"""Leitura de formulários HTML do SGP.

O envio parte dos valores que a página já traz e troca só os campos alterados,
como o navegador faria; campos novos do SGP seguem com o valor padrão.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Iterable, Iterator, Mapping, Sequence
from html import unescape
from html.parser import HTMLParser

from ..erros import OpcaoAmbigua, OpcaoNaoEncontrada

ValorCampo = str | Sequence[str] | None  # lista: select múltiplo; None: remove o campo


def _normalizar(texto: str) -> str:
    return " ".join(texto.split()).lower()


@dataclass(frozen=True)
class Opcao:
    valor: str
    rotulo: str


class ListaOpcoes(Sequence[Opcao]):
    def __init__(self, opcoes: Iterable[Opcao] = (), campo: str = ""):
        self._opcoes = tuple(opcoes)
        self.campo = campo

    def __getitem__(self, indice):
        return self._opcoes[indice]

    def __len__(self) -> int:
        return len(self._opcoes)

    def __iter__(self) -> Iterator[Opcao]:
        return iter(self._opcoes)

    def rotulos(self) -> list[str]:
        unicos: dict[str, str] = {}
        for opcao in self._opcoes:
            if opcao.valor:
                unicos.setdefault(_normalizar(opcao.rotulo), opcao.rotulo)
        return list(unicos.values())

    def resolver(self, texto: str, descricao: str | None = None) -> str:
        """Rótulo idêntico, depois que começa com ``texto``, depois que contém ``texto``."""
        rotulo_campo = descricao or self.campo
        alvo = _normalizar(texto)
        validas = [(o.valor, _normalizar(o.rotulo)) for o in self._opcoes if o.valor]
        exatas = [v for v, r in validas if r == alvo]
        if exatas:
            return exatas[0]
        for criterio in (str.startswith, str.__contains__):
            achadas = [v for v, r in validas if criterio(r, alvo)]
            if len(achadas) == 1:
                return achadas[0]
            if len(achadas) > 1:
                raise OpcaoAmbigua(rotulo_campo, texto, len(achadas))
        raise OpcaoNaoEncontrada(rotulo_campo, texto)

    def resolver_todos(self, texto: str, descricao: str | None = None) -> list[str]:
        # o SGP aceita nomes repetidos (vários POPs "Natal-RN"); no filtro entram todos
        alvo = _normalizar(texto)
        exatas = [o.valor for o in self._opcoes if o.valor and _normalizar(o.rotulo) == alvo]
        return exatas or [self.resolver(texto, descricao)]


@dataclass
class Formulario:
    campos: list[tuple[str, str]] = field(default_factory=list)
    opcoes: dict[str, ListaOpcoes] = field(default_factory=dict)

    @classmethod
    def de_html(cls, html: str) -> Formulario:
        leitor = _LeitorFormulario()
        leitor.feed(html)
        leitor.close()
        return cls(leitor.campos, leitor.opcoes)

    def opcoes_de(self, campo: str) -> ListaOpcoes:
        return self.opcoes.get(campo) or ListaOpcoes(campo=campo)

    def tem_campo(self, nome: str) -> bool:
        return nome in self.opcoes or any(n == nome for n, _ in self.campos)

    def valores_de(self, nome: str) -> list[str]:
        return [v for n, v in self.campos if n == nome]

    def preencher(self, alteracoes: Mapping[str, ValorCampo],
                  extras: Iterable[tuple[str, str]] = ()) -> list[tuple[str, str]]:
        dados = [(nome, valor) for nome, valor in self.campos if nome not in alteracoes]
        for nome, valor in alteracoes.items():
            if valor is None:
                continue
            valores = [valor] if isinstance(valor, str) else valor
            dados.extend((nome, str(v)) for v in valores)
        dados.extend(extras)
        return dados


class _LeitorFormulario(HTMLParser):
    _TIPOS_IGNORADOS = {"submit", "button", "image", "file", "reset"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.campos: list[tuple[str, str]] = []
        self.opcoes: dict[str, ListaOpcoes] = {}
        self._select: str | None = None
        self._select_multiplo = False
        self._opcoes_select: list[Opcao] = []
        self._selecionadas: list[str] = []
        self._opcao: list | None = None
        self._textarea: list | None = None

    def handle_starttag(self, tag, atributos):
        a = dict(atributos)
        nome = a.get("name")
        if tag == "input" and nome:
            self._input(nome, a)
        elif tag == "select" and nome:
            self._select, self._select_multiplo = nome, "multiple" in a
            self._opcoes_select, self._selecionadas = [], []
        elif tag == "option" and self._select:
            self._opcao = [a.get("value", ""), "", "selected" in a]
        elif tag == "textarea" and nome:
            self._textarea = [nome, ""]

    def _input(self, nome: str, a: dict):
        tipo = (a.get("type") or "text").lower()
        if tipo in self._TIPOS_IGNORADOS:
            return
        if tipo in ("checkbox", "radio"):
            if "checked" in a:
                self.campos.append((nome, a.get("value") or "on"))
            return
        self.campos.append((nome, a.get("value") or ""))

    def handle_data(self, dados):
        if self._opcao is not None:
            self._opcao[1] += dados
        elif self._textarea is not None:
            self._textarea[1] += dados

    def handle_endtag(self, tag):
        if tag == "option" and self._opcao is not None:
            self._fechar_opcao()
        elif tag == "select" and self._select:
            self._fechar_select()
        elif tag == "textarea" and self._textarea is not None:
            nome, valor = self._textarea
            self.campos.append((nome, valor[1:] if valor.startswith("\n") else valor))
            self._textarea = None

    def _fechar_opcao(self):
        assert self._opcao is not None
        valor, rotulo, selecionada = self._opcao
        self._opcoes_select.append(Opcao(valor, " ".join(rotulo.split())))
        if selecionada:
            self._selecionadas.append(valor)
        self._opcao = None

    def _fechar_select(self):
        nome = self._select
        assert nome is not None
        self.opcoes[nome] = ListaOpcoes(self._opcoes_select, campo=nome)
        if self._selecionadas:
            self.campos.extend((nome, v) for v in self._selecionadas)
        elif not self._select_multiplo and self._opcoes_select:
            self.campos.append((nome, self._opcoes_select[0].valor))
        self._select = None


_LISTA_ERROS = re.compile(r'<ul class="errorlist[^"]*">(.*?)</ul>', re.S)
_ITEM = re.compile(r"<li>(.*?)</li>", re.S)
# telas antigas: <strong>Campo</strong> &nbsp; <span class="fielderror">mensagem</span>
_ERRO_DE_CAMPO = re.compile(r'<strong>\s*([^<]+?)\s*</strong>\s*(?:&nbsp;\s*)*<span class="fielderror">(.*?)</span>', re.S)
_AVISO = re.compile(r'class="[^"]*(?:errornote|alert-danger|alert-error)[^"]*"[^>]*>(.*?)</', re.S)
_TAG = re.compile(r"<[^>]+>")
_GENERICAS = {"Por favor, corrija o erro abaixo.", "Por favor, corrija os erros abaixo."}


def extrair_erros(html: str) -> list[str]:
    mensagens = [item for bloco in _LISTA_ERROS.findall(html) for item in _ITEM.findall(bloco)]
    mensagens += [f"{campo}: {mensagem}" for campo, mensagem in _ERRO_DE_CAMPO.findall(html)]
    mensagens += _AVISO.findall(html)
    vistas: list[str] = []
    for bruta in mensagens:
        texto = " ".join(unescape(_TAG.sub("", bruta)).replace("\xa0", " ").split())
        if texto and texto not in _GENERICAS and texto not in vistas:
            vistas.append(texto)
    return vistas
