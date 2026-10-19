import unittest
from decimal import Decimal

from sgpcariap.dominio import Configuracao, formatar_br, nome_do_plano, para_decimal

from .apoio import configuracao_exemplo


class TestDinheiro(unittest.TestCase):
    def test_converte_formatos_comuns(self):
        casos = {"119,99": Decimal("119.99"), "R$ 1.234,56": Decimal("1234.56"), 119.9: Decimal("119.90")}
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(para_decimal(entrada), esperado)

    def test_valores_invalidos_viram_none(self):
        for entrada in (None, "", "abc", True):
            with self.subTest(entrada=entrada):
                self.assertIsNone(para_decimal(entrada))

    def test_formatacao_brasileira(self):
        self.assertEqual(formatar_br(Decimal("1234.5")), "1.234,50")


class TestMapeamento(unittest.TestCase):
    def test_nome_do_plano_sem_o_grupo(self):
        self.assertEqual(nome_do_plano("Fibra - 400_MEGA_FIBRA"), "400_MEGA_FIBRA")
        self.assertEqual(nome_do_plano("400_MEGA_FIBRA"), "400_MEGA_FIBRA")

    def test_servicos_por_plano(self):
        mapa = configuracao_exemplo().servicos_por_plano()
        self.assertEqual(mapa["600 mega"], ["E-book Super Essencial", "Audiobook Super Duo"])
        self.assertEqual(mapa["1gb"], ["E-book Super Duo"])

    def test_servicos_usados_sem_repetir(self):
        self.assertEqual(configuracao_exemplo().servicos_usados(),
                         ["Audiobook Super Duo", "E-book Super Duo", "E-book Super Essencial"])

    def test_problemas_do_mapeamento(self):
        config = configuracao_exemplo(grupos=[
            {"nome": "A", "planos": ["Fibra - 400 MEGA"], "servicos": ["X"]},
            {"nome": "B", "planos": ["Fibra - 400 MEGA"], "servicos": []},
            {"nome": "C", "planos": [], "servicos": ["Y"]},
        ])
        problemas = "\n".join(config.problemas())
        for trecho in ("está em dois grupos", "B: nenhum serviço", "C: nenhum plano"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, problemas)

    def test_padroes_do_lote(self):
        lote = Configuracao.de_dict({}).lote
        self.assertEqual((lote.status_contrato, lote.ativar, lote.pausa_segundos), (["Ativo"], True, 2))

    def test_ida_e_volta(self):
        original = configuracao_exemplo()
        self.assertEqual(Configuracao.de_dict(original.para_dict()), original)


if __name__ == "__main__":
    unittest.main()
