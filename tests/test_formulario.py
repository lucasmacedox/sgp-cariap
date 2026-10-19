import unittest

from sgpcariap.erros import OpcaoAmbigua, OpcaoNaoEncontrada
from sgpcariap.sgp import Formulario
from sgpcariap.sgp.formulario import extrair_erros

from .apoio import opcoes

HTML = """
<form method="post">
  <input type="hidden" name="csrfmiddlewaretoken" value="abc">
  <input type="text" name="descricao" value="">
  <input type="checkbox" name="ativo" checked>
  <input type="checkbox" name="precadastro">
  <input type="submit" name="_save" value="Salvar">
  <select name="tipo">
    <option value="">---------</option>
    <option value="1">SCM</option>
    <option value="2" selected>SVA</option>
  </select>
  <select name="pops" multiple>
    <option value="10" selected>Centro</option>
    <option value="11">Norte</option>
  </select>
  <select name="contrato"><option value="">---------</option><option value="5">Contrato &amp; TV</option></select>
  <textarea name="obs">
linha</textarea>
</form>
"""


class TestFormulario(unittest.TestCase):
    def setUp(self):
        self.formulario = Formulario.de_html(HTML)

    def test_le_campos_como_o_navegador_enviaria(self):
        self.assertEqual(self.formulario.campos, [
            ("csrfmiddlewaretoken", "abc"), ("descricao", ""), ("ativo", "on"),
            ("tipo", "2"), ("pops", "10"), ("contrato", ""), ("obs", "linha"),
        ])

    def test_rotulos_ignoram_a_opcao_vazia_e_decodificam_entidades(self):
        self.assertEqual(self.formulario.opcoes_de("contrato").rotulos(), ["Contrato & TV"])

    def test_preencher_substitui_remove_e_acrescenta(self):
        dados = self.formulario.preencher(
            {"descricao": "Plano", "ativo": None, "pops": ["10", "11"]},
            extras=[("_save", "Salvar")])
        self.assertIn(("descricao", "Plano"), dados)
        self.assertNotIn(("ativo", "on"), dados)
        self.assertEqual([v for n, v in dados if n == "pops"], ["10", "11"])
        self.assertEqual(dados[-1], ("_save", "Salvar"))
        self.assertIn(("csrfmiddlewaretoken", "abc"), dados)

    def test_campo_inexistente_devolve_lista_vazia(self):
        self.assertEqual(len(self.formulario.opcoes_de("nao_existe")), 0)
        self.assertTrue(self.formulario.tem_campo("tipo"))
        self.assertFalse(self.formulario.tem_campo("nao_existe"))


class TestResolverOpcao(unittest.TestCase):
    def setUp(self):
        self.contratos = opcoes("Contrato Fibra", "Contrato Fibra teste1", "TV Premium", "Rádio", campo="contrato")

    def test_texto_identico_tem_prioridade(self):
        self.assertEqual(self.contratos.resolver("contrato fibra"), "1")

    def test_inicio_unico(self):
        self.assertEqual(self.contratos.resolver("TV"), "3")

    def test_trecho_unico(self):
        self.assertEqual(self.contratos.resolver("premium"), "3")

    def test_ambiguo(self):
        with self.assertRaises(OpcaoAmbigua):
            self.contratos.resolver("Contrato")

    def test_inexistente(self):
        with self.assertRaises(OpcaoNaoEncontrada):
            self.contratos.resolver("Satélite")

    def test_nome_repetido_traz_todas_as_opcoes(self):
        pops = opcoes("Natal-RN", "Mossoró", " Natal-RN ", "Natal-RN Sul", campo="pops")
        self.assertEqual(pops.resolver_todos("natal-rn"), ["1", "3"])
        self.assertEqual(pops.resolver_todos("Sul"), ["4"])
        self.assertEqual(pops.rotulos(), ["Natal-RN", "Mossoró", "Natal-RN Sul"])
        with self.assertRaises(OpcaoNaoEncontrada):
            pops.resolver_todos("Recife")


class TestErrosDoSGP(unittest.TestCase):
    def test_extrai_mensagens_sem_repetir_e_sem_a_generica(self):
        html = """<p class="errornote">Por favor, corrija o erro abaixo.</p>
                  <ul class="errorlist"><li>Este campo é obrigatório.</li></ul>
                  <ul class="errorlist nonfield"><li>Necessário informar a <b>Unidade</b>.</li>
                  <li>Este campo é obrigatório.</li></ul>"""
        self.assertEqual(extrair_erros(html), ["Este campo é obrigatório.", "Necessário informar a Unidade."])


class TestErrosDeTelaAntiga(unittest.TestCase):
    def test_erro_com_nome_do_campo(self):
        html = """<strong> Plano de Internet </strong> &nbsp;
                  <span class="fielderror"> Este campo é obrigatório. &nbsp; </span>"""
        self.assertEqual(extrair_erros(html), ["Plano de Internet: Este campo é obrigatório."])


if __name__ == "__main__":
    unittest.main()
