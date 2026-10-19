"""Conferência de cadastro: regras, leitura da exportação do SGP e efeito no lote."""

import io
import unittest
import zipfile
from email.message import Message
from types import SimpleNamespace
from xml.sax.saxutils import escape

from sgpcariap.cadastro import ExecutorLote, ControleExecucao, MontadorLote, SituacaoItem, validar
from sgpcariap.cadastro.validacao import documento_valido, email_valido, tipo_telefone
from sgpcariap.erros import ErroSGP
from sgpcariap.sgp import ContatosCliente, Formulario, ListaOpcoes, Opcao
from sgpcariap.sgp.http import Resposta
from sgpcariap.sgp.planilha import linhas_xlsx
from sgpcariap.sgp.telas import TelaListaClientes

from .apoio import ObservadorMemoria, configuracao_exemplo
from .test_lote import ListaClientesFalsa, RelatorioFalso, ServicoTVFalso, _catalogo, _servico


def _coluna(indice: int) -> str:
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def xlsx(linhas: list[list[str]]) -> bytes:
    """Planilha mínima como a do SGP: textos compartilhados e células vazias omitidas."""
    textos: list[str] = []
    xml_linhas = []
    for n, linha in enumerate(linhas, 1):
        celulas = []
        for i, valor in enumerate(linha):
            if valor == "":
                continue
            textos.append(valor)
            celulas.append(f'<c r="{_coluna(i)}{n}" t="s"><v>{len(textos) - 1}</v></c>')
        xml_linhas.append(f'<row r="{n}">{"".join(celulas)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{escape(t)}</t></si>" for t in textos) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(xml_linhas)}</sheetData></worksheet>')
    return buffer.getvalue()


CABECALHO = ["Cliente ID", "Nome/Razão Social", "CPF/CNPJ", "Contrato ID", "Celulares", "Telefones", "Emails", "Senha"]


class TestRegras(unittest.TestCase):
    def test_email(self):
        for email in ("joao@gmail.com", "maria.silva+tv@provedor.net.br", "a_b@sub.dominio.com"):
            self.assertTrue(email_valido(email), email)
        for email in ("joao@gmail", "joao gmail.com", "joao@@gmail.com", "joao@gmail.con", "@gmail.com",
                      "joao.@gmail.com", "joao@-gmail.com", "sem email"):
            self.assertFalse(email_valido(email), email)

    def test_telefone(self):
        casos = {"(84) 99999-0001": "celular", "+55 84 99999-0001": "celular", "5584999990001": "celular",
                 "084999990001": "celular", "(84) 3222-1234": "fixo", "(84) 9999-0001": None,  # celular sem o 9
                 "99999-0001": None, "(00) 99999-0001": None, "(84) 99999-999": None, "(84) 99999-9999": None}
        for numero, esperado in casos.items():
            self.assertEqual(tipo_telefone(numero), esperado, numero)

    def test_documento(self):
        for doc in ("529.982.247-25", "52998224725", "11.222.333/0001-81"):
            self.assertTrue(documento_valido(doc), doc)
        for doc in ("529.982.247-26", "000.000.000-00", "11.222.333/0001-82", "5413092", ""):
            self.assertFalse(documento_valido(doc), doc)

    def test_cadastro_completo_nao_tem_pendencia(self):
        self.assertEqual(validar(ContatosCliente("1", "529.982.247-25", ("(84) 99999-0001",), (), ("a@b.com",))), [])

    def test_pendencias_que_bloqueiam(self):
        pendencias = validar(ContatosCliente("1", "000.000.000-00", (), ("(84) 9999-0001",), ()))
        self.assertEqual([(p.codigo, p.bloqueia) for p in pendencias],
                         [("documento_invalido", True), ("sem_email", True), ("celular_sem_9", True)])
        self.assertEqual(pendencias[2].detalhe, "(84) 9999-0001 → (84) 99999-0001")

    def test_so_telefone_fixo_bloqueia(self):
        pendencias = validar(ContatosCliente("1", "529.982.247-25", (), ("(84) 3222-1234",),
                                             ("joao@gmail.con", "joao@gmail.com")))
        self.assertEqual([(p.codigo, p.bloqueia) for p in pendencias], [("email_invalido", False), ("sem_celular", True)])

    def test_celular_com_9_basta(self):
        contatos = ContatosCliente("1", "529.982.247-25", ("(84) 9999-0001",),
                                   ("(84) 3222-1234", "(84) 99999-0001"), ("a@b.com",))
        self.assertEqual(validar(contatos), [])

    def test_telefone_invalido(self):
        pendencias = validar(ContatosCliente("1", "529.982.247-25", ("(84) 99999-9999", "3222-1234"), (), ("a@b.com",)))
        self.assertEqual([p.codigo for p in pendencias], ["telefone_invalido"])

    def test_contrato_fora_da_exportacao_vira_aviso(self):
        self.assertEqual([(p.codigo, p.bloqueia) for p in validar(None)], [("nao_conferido", False)])


class TestExportacaoClientes(unittest.TestCase):
    def test_le_planilha_com_celulas_vazias(self):
        self.assertEqual(linhas_xlsx(xlsx([["a", "", "c"], [], ["", "b"]])), [["a", "", "c"], [], ["", "b"]])

    def test_arquivo_que_nao_e_planilha(self):
        with self.assertRaises(ErroSGP):
            linhas_xlsx(b"<html>login</html>")

    def test_contatos_por_contrato(self):
        planilha = xlsx([
            ["Relatório de Clientes"], ["Quantidade de Clientes: 2"], CABECALHO,
            ["10", "Ana", "529.982.247-25", "100", "Celular Pessoal: (84) 99999-0001\nWhatsApp Número: (84) 98888-0002",
             "", "ana@exemplo.com", "segredo"],
            ["10", "Ana", "529.982.247-25", "100", "Celular Pessoal: (84) 99999-0001", "Telefone Residencial: (84) 3222-1234",
             "ana@exemplo.com", "segredo"],
            ["11", "Bia", "", "101", "", "", "", "segredo"],
        ])
        contatos = TelaListaClientes._ler(planilha)
        self.assertEqual(contatos["100"], ContatosCliente("10", "529.982.247-25", ("(84) 99999-0001", "(84) 98888-0002"),
                                                          ("(84) 3222-1234",), ("ana@exemplo.com",)))
        self.assertEqual(contatos["101"], ContatosCliente("11", ""))
        self.assertNotIn("segredo", repr(contatos))  # a coluna de senha nunca é lida

    def _tela(self, *respostas, pops=("Natal-RN",), planos=("1GB - Pós Pago - 1 Gb",)):
        """Tela com um SGP de mentira que devolve as ``respostas`` (tipo, corpo) em ordem."""
        formulario = Formulario(opcoes={"planointernet": ListaOpcoes([Opcao(str(244 + i), p) for i, p in enumerate(planos)]),
                                        "status": ListaOpcoes([Opcao("1", " Ativo ")]),
                                        "popservico": ListaOpcoes([Opcao(str(290 - i), p) for i, p in enumerate(pops)])})
        fila = list(respostas)
        pedidos = []

        def arquivo(caminho, timeout=None):
            pedidos.append(caminho)
            tipo, corpo = fila.pop(0)
            cabecalhos = Message()
            cabecalhos["Content-Type"] = tipo
            texto = corpo.decode("utf-8", "replace") if isinstance(corpo, bytes) else corpo
            return Resposta(200, caminho, texto, cabecalhos, corpo if isinstance(corpo, bytes) else corpo.encode())

        cliente = SimpleNamespace(formulario=lambda rota: formulario, arquivo=arquivo)
        return TelaListaClientes(cliente), pedidos

    def test_filtro_sem_clientes_devolve_a_pagina_e_vira_lista_vazia(self):
        tela, pedidos = self._tela(("text/html; charset=utf-8", '<a href="/admin/cliente/list/">Clientes</a>'))
        self.assertEqual(tela.contatos(["1GB"], status_contrato=["Ativo"]), {})
        self.assertIn("planointernet=244&status=1&printexcel=true", pedidos[0])

    def test_pagina_com_clientes_no_lugar_da_planilha_e_erro(self):
        tela, _ = self._tela(("text/html", '<a href="/admin/cliente/3070/edit/">Ana</a>'))
        with self.assertRaisesRegex(ErroSGP, "em vez de exportar"):
            tela.contatos(["1GB"])

    def test_pop_com_nome_repetido_filtra_por_todos(self):
        tela, pedidos = self._tela(("text/html", ""), pops=("Natal-RN", "Mossoró", "Natal-RN"))
        tela.contatos(["1GB"], pops=["Natal-RN"])
        self.assertIn("popservico=290&popservico=288&printexcel", pedidos[0])

    def test_plano_com_nome_repetido_exporta_os_dois(self):
        planos = ("1GB - Pós Pago - 1 Gb", "1GB Plus - Pós Pago - 1 Gb", "1GB - Pós Pago - 1 Gb - Valor R$ 99,90")
        tela, pedidos = self._tela(("text/html", ""), ("text/html", ""), planos=planos)
        tela.contatos(["1GB"])
        self.assertEqual([p.split("planointernet=")[1][:3] for p in pedidos], ["244", "246"])

    def test_exportacao_em_excel(self):
        planilha = xlsx([CABECALHO, ["10", "Ana", "529.982.247-25", "100", "(84) 99999-0001", "", "ana@exemplo.com", "x"]])
        tela, _ = self._tela(("application/ms-excel", planilha))
        self.assertEqual(tela.contatos(["1GB"])["100"].emails, ("ana@exemplo.com",))

    def test_exportacao_sem_as_colunas_esperadas(self):
        with self.assertRaisesRegex(ErroSGP, "Emails"):
            TelaListaClientes._ler(xlsx([[c for c in CABECALHO if c != "Emails"]]))


class TestLoteComConferencia(unittest.TestCase):
    def _montar(self, clientes, **lote):
        relatorio = RelatorioFalso(internet=[_servico("1", "10", "1GB"), _servico("2", "11", "1GB")])
        config = configuracao_exemplo(lote={"pausa_segundos": 0, **lote})
        return MontadorLote(_catalogo(relatorio, clientes=clientes), config).montar()

    def test_cadastro_com_pendencia_fica_de_fora(self):
        clientes = ListaClientesFalsa({"10": ContatosCliente("7", "529.982.247-25", (), (), ())})
        itens = {i.contrato_id: i for i in self._montar(clientes)}
        self.assertEqual(itens["10"].situacao, SituacaoItem.BLOQUEADO)
        self.assertEqual(itens["10"].mensagem, "Sem e-mail, Sem telefone")
        self.assertEqual(itens["10"].para_dict()["cliente_id"], "7")
        self.assertEqual(itens["11"].situacao, SituacaoItem.PENDENTE)
        self.assertEqual(clientes.consultas, [(["1GB"], [], ["Ativo"])])

        servico_tv = ServicoTVFalso()
        executor = ExecutorLote(_catalogo(servico_tv=servico_tv), configuracao_exemplo(lote={"pausa_segundos": 0}),
                                ObservadorMemoria(), ControleExecucao())
        executor.executar(list(itens.values()))
        self.assertEqual(servico_tv.adicionados, [("11", "E-book Super Duo")])

    def test_conferencia_desligada_nao_consulta(self):
        clientes = ListaClientesFalsa({"10": ContatosCliente("7", "", (), (), ())})
        itens = self._montar(clientes, validar_cadastro=False)
        self.assertEqual(({i.situacao for i in itens}, clientes.consultas), ({SituacaoItem.PENDENTE}, []))

    def test_falha_na_exportacao_vira_aviso_sem_interromper_a_busca(self):
        itens = self._montar(ListaClientesFalsa(erro=ErroSGP("tempo esgotado")))
        self.assertEqual({i.situacao for i in itens}, {SituacaoItem.PENDENTE})
        pendencia = itens[0].pendencias[0]
        self.assertEqual((pendencia.codigo, pendencia.bloqueia), ("nao_conferido", False))
        self.assertIn("tempo esgotado", pendencia.detalhe)


if __name__ == "__main__":
    unittest.main()
