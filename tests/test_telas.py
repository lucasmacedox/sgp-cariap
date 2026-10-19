"""Telas contra páginas com a estrutura do SGP 1.0.251."""

import unittest
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from sgpcariap.erros import ErroIdentificacao, ErroPlanoIndisponivel
from sgpcariap.sgp import FiltroServicos, NovoServicoTV
from sgpcariap.sgp.formulario import Formulario
from sgpcariap.sgp.telas import TelaListaPlanos, TelaRelatorioServicos, TelaServicoTV


def _select(nome, opcoes, selecionadas=(), multiplo=False):
    itens = "".join(f'<option value="{v}"{" selected" if v in selecionadas else ""}>{r}</option>' for v, r in opcoes)
    return f'<select name="{nome}"{" multiple" if multiplo else ""}><option value="">---------</option>{itens}</select>'


class ClienteFalso:
    """Responde páginas por caminho (ou função do caminho) e guarda os envios."""

    def __init__(self, paginas):
        self.paginas = paginas
        self.lidas: list[str] = []
        self.envios: list[tuple[str, list]] = []
        self.destino = "/admin/cliente/77/contratos/"

    def pagina(self, caminho):
        self.lidas.append(caminho)
        resposta = self.paginas.get(caminho.split("?")[0])
        return resposta(caminho) if callable(resposta) else resposta

    def pagina_e_endereco(self, caminho):
        return self.pagina(caminho), f"https://sgp.exemplo{caminho}"

    def formulario(self, caminho):
        return Formulario.de_html(self.pagina(caminho))

    def enviar(self, caminho, alteracoes, extras=(), formulario=None):
        self.envios.append((caminho, (formulario or self.formulario(caminho)).preencher(alteracoes, extras)))
        aposenviar = self.paginas.get("depois_de_enviar")
        if aposenviar:
            aposenviar()
        return self.destino


LISTA_INTERNET = """<table>
<tr><th>#</th><th>Descrição</th><th>Grupo</th><th>Preço</th><th>Ativo</th><th>Total</th><th>Total</th></tr>
<tr><td><a href="/admin/plano/111/edit/">111</a></td><td>500 mega Fidelidade</td><td>Fibra</td>
    <td>R$ 1.099,90</td><td>12</td><td>15</td><td>R$ 16.498,50</td></tr>
<tr><td><a href="/admin/plano/120/edit/">120</a></td><td>Plano &amp; Cia</td><td>Rádio</td>
    <td>-</td><td></td><td>0</td><td>R$ 0,00</td></tr>
</table>"""

LISTA_TV = """<table>
<tr><th>#</th><th>Descrição</th><th>Grupo</th><th>Preço</th><th>Ativos</th><th>Total</th><th>Gateway</th></tr>
<tr><td><a href="/admin/plano/352/edit/">352</a></td><td>Cariap E-book Duo</td><td>TV</td>
    <td>R$ 9,90</td><td>3</td><td>4</td><td>Cariap V2</td></tr>
</table>"""


class TestListaPlanos(unittest.TestCase):
    def setUp(self):
        pops = _select("form1-pops", [("19", "Natal-RN"), ("20", "Mossoró-RN")], selecionadas={"19", "20"}, multiplo=True)
        self.tela = TelaListaPlanos(ClienteFalso({
            "/admin/plano/internet/": LISTA_INTERNET, "/admin/plano/tv/": LISTA_TV,
            "/admin/plano/352/edit/": f"<form>{pops}</form>", "/admin/plano/353/edit/": "<form></form>"}))

    def test_internet_le_preco_e_clientes(self):
        primeiro, segundo = self.tela.internet()
        self.assertEqual((primeiro.id, primeiro.nome, primeiro.grupo, primeiro.preco, primeiro.ativos),
                         ("111", "500 mega Fidelidade", "Fibra", Decimal("1099.90"), 12))
        self.assertEqual((segundo.nome, segundo.preco, segundo.ativos), ("Plano & Cia", None, 0))

    def test_tv_traz_o_gateway(self):
        (plano,) = self.tela.tv()
        self.assertEqual((plano.id, plano.nome, plano.ativos, plano.gateway), ("352", "Cariap E-book Duo", 3, "Cariap V2"))

    def test_pops_do_plano(self):
        self.assertEqual(self.tela.pops("352"), ["19", "20"])
        self.assertEqual(self.tela.pops("353"), [])


FORM_RELATORIO = "<form>" + "".join([
    _select("tipo_servico", [("1", "Internet"), ("2", "TV")]),
    _select("planos_internet", [("111", "500 mega Fidelidade - Pós Pago - 500 Mb"),
                                ("120", "500 mega Fidelidade - Pós Pago - 600 Mb"),
                                ("130", "1GB - Pós Pago - 1 Gb")], multiplo=True),
    _select("planos_tv", [("352", "Cariap E-book Duo - Pós Pago")], multiplo=True),
    _select("pops", [("19", "Natal-RN"), ("192", "Natal-RN"), ("20", "Mossoró-RN")], multiplo=True),
    _select("contrato_status", [("1", "Ativo"), ("2", "Inativo")], multiplo=True),
    _select("servico_status", [("1", "Ativo")], multiplo=True),
    '<input name="paginate_by" value="25">',
]) + "</form>"


def _linha_relatorio(servico_id, contrato, cliente, plano, situacao="Ativo", tipo="internet"):
    return (f'<tr><td><a href="/admin/servicos/{tipo}/{servico_id}/">{servico_id}</a></td><td>{tipo.title()}</td>'
            f"<td>{contrato} - {cliente}</td><td>{plano}</td><td>Natal-RN</td><td>01/01/2026</td>"
            f"<td>login{servico_id}</td><td></td><td>{situacao}</td></tr>")


class TestRelatorioServicos(unittest.TestCase):
    def _tela(self, paginas):
        def relatorio(caminho):
            consulta = parse_qs(urlsplit(caminho).query)
            if "page" not in consulta:  # leitura do formulário, sem filtros
                return FORM_RELATORIO
            self.consultas.append(consulta)
            return FORM_RELATORIO + "<table>" + "".join(paginas.get(consulta["page"][0], [])) + "</table>"

        self.consultas: list[dict] = []
        tela = TelaRelatorioServicos(ClienteFalso({"/admin/relatorios/contrato/servico/": relatorio}))
        tela._POR_PAGINA = "2"
        return tela

    def test_filtros_viram_ids_com_nomes_repetidos_e_lista_e_paginada(self):
        tela = self._tela({
            "1": [_linha_relatorio("1", "2447", "ZZ-ROBO", "500 mega Fidelidade"),
                  _linha_relatorio("2", "2448", "Fulano - Filial", "1GB")],
            "2": [_linha_relatorio("3", "2449", "Ciclano", "1GB", situacao="Suspenso")],
        })
        servicos = tela.buscar(FiltroServicos(planos_internet=["500 mega Fidelidade"], pops=["Natal-RN"],
                                              status_contrato=["Ativo"]))
        filtros = self.consultas[0]
        self.assertEqual((filtros["tipo_servico"], filtros["planos_internet"], filtros["pops"], filtros["contrato_status"]),
                         (["1"], ["111", "120"], ["19", "192"], ["1"]))
        self.assertEqual([c["page"] for c in self.consultas], [["1"], ["2"]])
        self.assertEqual([(s.servico_id, s.contrato_id, s.cliente, s.situacao) for s in servicos],
                         [("1", "2447", "ZZ-ROBO", "Ativo"), ("2", "2448", "Fulano - Filial", "Ativo"),
                          ("3", "2449", "Ciclano", "Suspenso")])

    def test_pagina_repetida_encerra_a_leitura(self):
        mesma = [_linha_relatorio("1", "2447", "A", "1GB"), _linha_relatorio("2", "2448", "B", "1GB")]
        servicos = self._tela({"1": mesma, "2": mesma, "3": mesma}).buscar(FiltroServicos())
        self.assertEqual((len(servicos), len(self.consultas)), (2, 2))

    def test_campos_ausentes_indicam_outra_versao_do_sgp(self):
        self.assertEqual(self._tela({}).campos_ausentes(), [])
        tela = TelaRelatorioServicos(ClienteFalso({"/admin/relatorios/contrato/servico/": "<form></form>"}))
        self.assertEqual(tela.campos_ausentes(), list(TelaRelatorioServicos.CAMPOS))

    def test_opcoes_do_filtro_sem_repetir_nomes(self):
        opcoes = self._tela({}).opcoes_filtro()
        self.assertEqual((opcoes["planos_internet"], opcoes["pops"]),
                         (["500 mega Fidelidade", "1GB"], ["Natal-RN", "Mossoró-RN"]))


FORM_TV = ('<form><a href="/admin/cliente/77/">cliente</a>'
           + _select("servicot-grupo", [("5", "TV")])
           + _select("servicot-plano", [("352", "Cariap E-book Duo - R$ 9,90")])
           + _select("servicot-modoaquisicao", [("1", "Comodato"), ("2", "Venda")])
           + '<input type="checkbox" name="servicot-os_instalacao" checked>'
           + '<input name="enderecoinst-cep" value=""></form>')

SERVICO_INTERNET = ('<form><input name="enderecoinst-cep" value="59000-000">'
                    '<input name="enderecoinst-logradouro" value="Rua A"><input name="enderecoinst-numero" value="10">'
                    '<input name="enderecoinst-cidade" value="Natal"></form>')


def _contratos(*ids):
    return "".join(f'<a href="/admin/servicos/tv/{i}/">TV {i}</a>' for i in ids)


class TestServicoTV(unittest.TestCase):
    def _tela(self, antes, depois, form=FORM_TV):
        estado = {"contratos": _contratos(*antes)}
        paginas = {"/admin/clientecontrato/2447/tv/add/": form,
                   "/admin/cliente/77/contratos/": lambda _: estado["contratos"],
                   "depois_de_enviar": lambda: estado.update(contratos=_contratos(*depois))}
        self.cliente = ClienteFalso(paginas)
        return TelaServicoTV(self.cliente)

    def _novo(self, plano="Cariap E-book Duo"):
        return NovoServicoTV(grupo="TV", plano=plano, endereco={"cep": "59000-000", "cidade": "Natal"})

    def test_adicionar_envia_o_formulario_e_descobre_o_id_novo(self):
        tela = self._tela(antes=["200"], depois=["200", "239"])
        self.assertEqual(tela.adicionar("2447", self._novo()), "239")
        caminho, dados = self.cliente.envios[0]
        enviados = dict(dados)
        self.assertEqual(caminho, "/admin/clientecontrato/2447/tv/add/")
        self.assertEqual((enviados["servicot-grupo"], enviados["servicot-plano"], enviados["servicot-modoaquisicao"],
                          enviados["enderecoinst-cep"], enviados["enderecoinst-cidade"]),
                         ("5", "352", "1", "59000-000", "Natal"))
        self.assertNotIn("servicot-os_instalacao", enviados)  # não gera OS de instalação

    def test_sem_servico_novo_nao_inventa_id(self):
        tela = self._tela(antes=["200"], depois=["200"])
        with self.assertRaises(ErroIdentificacao):
            tela.adicionar("2447", self._novo())

    def test_plano_fora_do_pop_do_contrato(self):
        tela = self._tela(antes=[], depois=[])
        with self.assertRaises(ErroPlanoIndisponivel):
            tela.adicionar("2447", self._novo("Outro Plano"))
        self.assertEqual(self.cliente.envios, [])

    def test_endereco_de_instalacao_vem_do_servico_de_internet(self):
        tela = TelaServicoTV(ClienteFalso({"/admin/servicos/internet/900/": SERVICO_INTERNET}))
        endereco = tela.endereco_de_instalacao("900")
        self.assertEqual((endereco["cep"], endereco["numero"], endereco["bairro"]), ("59000-000", "10", ""))

    def test_ativar_le_a_situacao_na_pagina_devolvida(self):
        cliente = ClienteFalso({"/admin/servicos/tv/239/ativar": '<a href="/admin/servicos/tv/239/desativar">Desativar</a>'})
        self.assertTrue(TelaServicoTV(cliente).ativar("239"))
        self.assertEqual(cliente.lidas, ["/admin/servicos/tv/239/ativar"])  # nunca desativar nem excluir

    def test_ativar_que_nao_pegou(self):
        cliente = ClienteFalso({"/admin/servicos/tv/239/ativar": '<a href="/admin/servicos/tv/239/ativar">Ativar</a>'})
        self.assertFalse(TelaServicoTV(cliente).ativar("239"))


if __name__ == "__main__":
    unittest.main()
