import unittest
from dataclasses import dataclass, field
from types import SimpleNamespace

from sgpcariap.cadastro import ControleExecucao, ExecutorLote, MontadorLote, SituacaoItem
from sgpcariap.erros import ErroAssistente, ErroConexao, ErroFormulario, ErroPlanoIndisponivel
from sgpcariap.sgp import ContatosCliente, ServicoContratado

from .apoio import ObservadorMemoria, configuracao_exemplo


def _servico(servico_id, contrato, plano, situacao="Ativo"):
    return ServicoContratado(servico_id, contrato, f"Cliente {contrato}", plano, situacao)


@dataclass
class RelatorioFalso:
    internet: list
    tv: list = field(default_factory=list)
    filtros: list = field(default_factory=list)

    def buscar(self, filtro):
        self.filtros.append(filtro)
        return self.internet if filtro.tipo == "Internet" else self.tv


@dataclass
class ServicoTVFalso:
    recusar: set = field(default_factory=set)      # serviços que o SGP recusa
    nao_ativa: set = field(default_factory=set)    # serviços cuja ativação não conclui
    adicionados: list = field(default_factory=list)
    ativados: list = field(default_factory=list)

    def endereco_de_instalacao(self, servico_internet_id):
        return {"cep": "59000-000"}

    def adicionar(self, contrato_id, novo):
        if novo.plano in self.recusar:
            raise ErroFormulario(["Plano de TV: Este campo é obrigatório."])
        self.adicionados.append((contrato_id, novo.plano))
        return f"{contrato_id}:{novo.plano}"

    def ativar(self, servico_id):
        self.ativados.append(servico_id)
        return servico_id.split(":", 1)[-1] not in self.nao_ativa


CADASTRO_OK = ContatosCliente("1", "529.982.247-25", ("(84) 99999-0001",), (), ("cliente@exemplo.com.br",))


@dataclass
class ListaClientesFalsa:
    """Contatos por contrato; quem não estiver em ``cadastros`` tem cadastro em ordem."""

    cadastros: dict = field(default_factory=dict)
    consultas: list = field(default_factory=list)
    erro: Exception | None = None

    def contatos(self, planos, pops=(), status_contrato=()):
        self.consultas.append((planos, list(pops), list(status_contrato)))
        if self.erro:
            raise self.erro
        return self

    def __contains__(self, contrato):
        return True

    def __getitem__(self, contrato):
        return self.cadastros.get(contrato, CADASTRO_OK)


def _catalogo(relatorio=None, servico_tv=None, pops=None, clientes=None, incompatibilidades=()):
    """``pops``: plano de TV → POPs; planos fora dele não são verificados."""
    pops = pops or {}
    planos = [SimpleNamespace(id=nome, nome=nome) for nome in pops]
    lista = SimpleNamespace(pops=lambda plano_id: pops[plano_id])
    return SimpleNamespace(planos_servico=planos, cliente=SimpleNamespace(versao_sgp="1.0.251"), telas=SimpleNamespace(
        relatorio_servicos=relatorio, servico_tv=servico_tv or ServicoTVFalso(), lista_planos=lista,
        lista_clientes=clientes if clientes is not None else ListaClientesFalsa(),
        incompatibilidades=lambda cadastro: list(incompatibilidades)))


class TestMontadorLote(unittest.TestCase):
    def test_compara_o_que_o_contrato_tem_com_o_que_o_grupo_pede(self):
        relatorio = RelatorioFalso(
            internet=[_servico("1", "10", "400 MEGA"), _servico("2", "20", "600 MEGA"), _servico("3", "30", "1GB"),
                      _servico("4", "40", "400 MEGA"), _servico("5", "10", "400 MEGA")],
            tv=[_servico("a", "20", "E-book Super Essencial"), _servico("b", "20", "Audiobook Super Duo"),
                _servico("c", "30", "E-book Super Duo", "Inativo"), _servico("d", "40", "E-book Super Essencial")])
        itens = {i.contrato_id: i for i in MontadorLote(_catalogo(relatorio), configuracao_exemplo()).montar()}
        self.assertEqual(len(itens), 4)  # contrato 10 com dois serviços de internet vira um item
        self.assertEqual(itens["10"].faltando, ["E-book Super Essencial", "Audiobook Super Duo"])
        self.assertEqual(itens["20"].situacao, SituacaoItem.COMPLETO)
        self.assertEqual((itens["30"].faltando, itens["30"].inativos), ([], {"E-book Super Duo": "c"}))
        self.assertEqual(itens["40"].faltando, ["Audiobook Super Duo"])

    def test_filtros_enviados_ao_relatorio(self):
        relatorio = RelatorioFalso(internet=[])
        MontadorLote(_catalogo(relatorio), configuracao_exemplo()).montar()
        internet, tv = relatorio.filtros
        self.assertEqual((internet.planos_internet, internet.status_contrato), (["1GB", "400 MEGA", "600 MEGA"], ["Ativo"]))
        self.assertEqual(tv.planos_tv, ["Audiobook Super Duo", "E-book Super Duo", "E-book Super Essencial"])

    def test_restringe_aos_planos_escolhidos(self):
        relatorio = RelatorioFalso(internet=[])
        config = configuracao_exemplo(lote={"planos": ["Fibra - 1GB"], "pops": ["Natal-RN"]})
        MontadorLote(_catalogo(relatorio), config).montar()
        self.assertEqual((relatorio.filtros[0].planos_internet, relatorio.filtros[0].pops), (["1GB"], ["Natal-RN"]))

    def test_avisa_plano_de_tv_sem_pop_antes_de_consultar_clientes(self):
        relatorio = RelatorioFalso(internet=[_servico("1", "10", "400 MEGA")])
        catalogo = _catalogo(relatorio, pops={"E-book Super Essencial": [], "Audiobook Super Duo": ["4"]})
        with self.assertRaisesRegex(ErroAssistente, "sem POP.*E-book Super Essencial"):
            MontadorLote(catalogo, configuracao_exemplo()).montar()
        self.assertEqual(relatorio.filtros, [])

    def test_sgp_com_telas_diferentes_para_antes_de_ler_a_base(self):
        relatorio = RelatorioFalso(internet=[])
        catalogo = _catalogo(relatorio, incompatibilidades=["Relatórios sem os campos pops"])
        with self.assertRaisesRegex(ErroAssistente, r"versão 1\.0\.251.*sem os campos pops"):
            MontadorLote(catalogo, configuracao_exemplo()).montar()
        self.assertEqual(relatorio.filtros, [])

    def test_recusa_mapeamento_com_problema(self):
        config = configuracao_exemplo(grupos=[{"nome": "A", "planos": ["Fibra - 1GB"], "servicos": []}])
        with self.assertRaises(ErroAssistente):
            MontadorLote(_catalogo(RelatorioFalso(internet=[])), config).montar()


class TestExecutorLote(unittest.TestCase):
    def _itens(self, *contratos, plano="400 MEGA"):
        relatorio = RelatorioFalso(internet=[_servico(str(i), c, plano) for i, c in enumerate(contratos)])
        return MontadorLote(_catalogo(relatorio), configuracao_exemplo()).montar()

    def _executar(self, itens, tv, **lote):
        config = configuracao_exemplo(lote={"pausa_segundos": 0, **lote})
        return ExecutorLote(_catalogo(None, tv), config, ObservadorMemoria(), ControleExecucao()).executar(itens)

    def test_adiciona_e_ativa_cada_servico(self):
        tv = ServicoTVFalso()
        itens = self._itens("10")
        resumo = self._executar(itens, tv)
        self.assertEqual(tv.adicionados, [("10", "E-book Super Essencial"), ("10", "Audiobook Super Duo")])
        self.assertEqual(len(tv.ativados), 2)
        self.assertEqual((itens[0].situacao, resumo.concluidos), (SituacaoItem.CONCLUIDO, 1))

    def test_falha_num_servico_nao_impede_os_outros(self):
        tv = ServicoTVFalso(recusar={"E-book Super Essencial"}, nao_ativa={"Audiobook Super Duo"})
        itens = self._itens("10", "20")
        resumo = self._executar(itens, tv)
        self.assertEqual(len(tv.adicionados), 2)  # um por contrato (o outro foi recusado)
        self.assertEqual(resumo.erros, 2)
        self.assertIn("CPF", itens[0].mensagem)
        self.assertEqual(itens[0].faltando, ["E-book Super Essencial"])  # continua pendente para a próxima vez

    def test_sem_ativar_so_adiciona(self):
        tv = ServicoTVFalso()
        itens = self._itens("10")
        self._executar(itens, tv, ativar=False)
        self.assertEqual((itens[0].situacao, tv.ativados), (SituacaoItem.CONCLUIDO, []))

    def test_limite_para_piloto(self):
        tv = ServicoTVFalso()
        self._executar(self._itens("10", "20", "30", plano="1GB"), tv, limite=2)
        self.assertEqual(len(tv.adicionados), 2)

    def test_parada_interrompe_antes_do_proximo_contrato(self):
        tv = ServicoTVFalso()
        controle = ControleExecucao()
        original = tv.ativar
        tv.ativar = lambda sid: (original(sid), controle.parar())
        itens = self._itens("10", "20", "30", plano="1GB")
        config = configuracao_exemplo(lote={"pausa_segundos": 0})
        ExecutorLote(_catalogo(None, tv), config, ObservadorMemoria(), controle).executar(itens)
        self.assertEqual(len(tv.adicionados), 1)
        self.assertEqual(sum(i.situacao is SituacaoItem.PENDENTE for i in itens), 2)


class TestFalhas(unittest.TestCase):
    def _executar(self, tv, *contratos, **lote):
        relatorio = RelatorioFalso(internet=[_servico(str(i), c, "1GB") for i, c in enumerate(contratos)])
        itens = MontadorLote(_catalogo(relatorio), configuracao_exemplo()).montar()
        observador = ObservadorMemoria()
        config = configuracao_exemplo(lote={"pausa_segundos": 0, **lote})
        ExecutorLote(_catalogo(None, tv), config, observador, ControleExecucao()).executar(itens)
        return itens, observador

    def test_falhas_classificadas_com_orientacao(self):
        tv = ServicoTVFalso()
        tv.adicionar = lambda contrato, novo: (_ for _ in ()).throw(ErroPlanoIndisponivel("fora do POP"))
        itens, _ = self._executar(tv, "10")
        falha = itens[0].para_dict()["falhas"][0]
        self.assertEqual((itens[0].situacao, falha["causa"], falha["titulo"]), (SituacaoItem.ERRO, "pop", "Plano fora do POP"))
        self.assertIn("POP", falha["orientacao"])

    def test_para_depois_de_falhas_gerais_seguidas(self):
        tv = ServicoTVFalso()
        tv.endereco_de_instalacao = lambda servico: (_ for _ in ()).throw(ErroConexao("sem resposta"))
        itens, observador = self._executar(tv, "10", "20", "30", "40", "50")
        situacoes = [i.situacao for i in itens]
        self.assertEqual(situacoes.count(SituacaoItem.ERRO), ExecutorLote.LIMITE_FALHAS_GERAIS)
        self.assertEqual(situacoes.count(SituacaoItem.PENDENTE), 5 - ExecutorLote.LIMITE_FALHAS_GERAIS)
        self.assertTrue(any("Interrompido" in m for m, _ in observador.mensagens))

    def test_falha_de_um_cliente_nao_conta_para_a_parada(self):
        tv = ServicoTVFalso(recusar={"E-book Super Duo"})
        itens, _ = self._executar(tv, "10", "20", "30", "40")
        self.assertEqual([i.situacao for i in itens].count(SituacaoItem.ERRO), 4)

    def test_etapas_informadas_durante_o_contrato(self):
        tv = ServicoTVFalso()
        etapas = []
        observador = ObservadorMemoria()
        observador.passo_atualizado = lambda indice, item: etapas.append(item.etapa)
        relatorio = RelatorioFalso(internet=[_servico("1", "10", "400 MEGA")])
        itens = MontadorLote(_catalogo(relatorio), configuracao_exemplo()).montar()
        ExecutorLote(_catalogo(None, tv), configuracao_exemplo(lote={"pausa_segundos": 0}), observador,
                     ControleExecucao(), relogio=iter([0.0, 4.5]).__next__).executar(itens)
        self.assertEqual(etapas[:4], ["Preparando", "Lendo endereço", "Adicionando E-book Super Essencial (1/2)",
                                      "Adicionando Audiobook Super Duo (2/2)"])
        self.assertIn("Ativando Audiobook Super Duo", etapas)
        self.assertEqual((etapas[-1], itens[0].duracao), ("", 4.5))


if __name__ == "__main__":
    unittest.main()
