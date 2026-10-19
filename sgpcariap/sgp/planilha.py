"""Leitura das planilhas Excel (.xlsx) exportadas pelo SGP, só com a biblioteca padrão.

Um .xlsx é um zip com XML. Basta a primeira planilha, como texto: os textos
repetidos ficam em ``sharedStrings.xml`` e cada célula aponta para eles. Células
vazias não aparecem no XML, por isso a coluna vem da referência (``B7``), não
da posição.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

from ..erros import ErroSGP

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_COLUNA = re.compile(r"[A-Z]+")
_LIMITE_BYTES = 512 * 1024 * 1024  # planilha descompactada; acima disso não é uma exportação comum


def linhas_xlsx(dados: bytes) -> list[list[str]]:
    """Linhas da primeira planilha, com as células como texto (vazias como "")."""
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ErroSGP("o SGP não devolveu uma planilha Excel") from None
    with arquivo:
        textos = _textos_compartilhados(arquivo)
        planilha = _ler_xml(arquivo, _primeira_planilha(arquivo))
    linhas = []
    for linha in planilha.iter(f"{_NS}row"):
        celulas: dict[int, str] = {}
        for celula in linha.iter(f"{_NS}c"):
            achado = _COLUNA.match(celula.get("r", ""))
            indice = _indice(achado.group(0)) if achado else len(celulas)
            celulas[indice] = _valor(celula, textos)
        linhas.append([celulas.get(i, "") for i in range(max(celulas, default=-1) + 1)])
    return linhas


def _primeira_planilha(arquivo: zipfile.ZipFile) -> str:
    nomes = sorted(n for n in arquivo.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    if not nomes:
        raise ErroSGP("a planilha exportada pelo SGP está vazia")
    return "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in nomes else nomes[0]


def _ler_xml(arquivo: zipfile.ZipFile, nome: str) -> ElementTree.Element:
    if arquivo.getinfo(nome).file_size > _LIMITE_BYTES:
        raise ErroSGP("a planilha exportada pelo SGP é grande demais")
    return ElementTree.fromstring(arquivo.read(nome))


def _textos_compartilhados(arquivo: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in arquivo.namelist():
        return []
    raiz = _ler_xml(arquivo, "xl/sharedStrings.xml")
    return ["".join(t.text or "" for t in item.iter(f"{_NS}t")) for item in raiz.iter(f"{_NS}si")]


def _valor(celula: ElementTree.Element, textos: list[str]) -> str:
    tipo = celula.get("t", "")
    if tipo == "inlineStr":
        return "".join(t.text or "" for t in celula.iter(f"{_NS}t"))
    valor = celula.findtext(f"{_NS}v") or ""
    if tipo == "s":
        return textos[int(valor)] if valor.isdigit() and int(valor) < len(textos) else ""
    return valor


def _indice(coluna: str) -> int:
    """A → 0, Z → 25, AA → 26."""
    indice = 0
    for letra in coluna:
        indice = indice * 26 + ord(letra) - ord("A") + 1
    return indice - 1
