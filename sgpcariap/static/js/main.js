// Montagem da aplicação: cria o estado compartilhado e as telas.

import { ClienteApi } from './api.js';
import { Combobox } from './componentes/combobox.js';
import { Dicas } from './componentes/dica.js';
import { Estado } from './estado.js';
import { Navegacao } from './navegacao.js';
import { TourGuiado } from './tour.js';
import { TelaConexao } from './telas/conexao.js';
import { TelaLote } from './telas/lote.js';
import { TelaMapeamento } from './telas/mapeamento.js';
import { ArquivoConfiguracao, MenuAjuda, SeletorProvedor } from './telas/topo.js';
import { $, Avisos } from './util.js';

async function iniciar() {
  const estado = new Estado();
  const api = new ClienteApi();
  const navegacao = new Navegacao(estado);
  const avisos = new Avisos($('#toast'));
  const contexto = { estado, api, navegacao, avisos };
  new Combobox();
  new Dicas();

  const seletorProvedor = new SeletorProvedor(contexto);
  new ArquivoConfiguracao(contexto, seletorProvedor);
  const conexao = new TelaConexao(contexto);
  new TelaMapeamento(contexto);
  new TelaLote(contexto);
  const tour = new TourGuiado(navegacao);
  const menu = new MenuAjuda(contexto, { tour, seletorProvedor });

  navegacao.mostrar(location.hash.slice(1) || 'conexao');
  navegacao.atualizarContadores();
  await retomarConexao(estado, api, menu, conexao);
  tour.abrirNaPrimeiraVisita();
}

/** Reaproveita a conexão do servidor só se ela for do SGP do provedor atual. */
async function retomarConexao(estado, api, menu, conexao) {
  try {
    const situacao = await api.status();
    menu.mostrarVersao(situacao.versao, situacao.dados);
    if (!situacao.conectado) return;
    if (situacao.url === estado.config.sgp.url) {
      estado.definirConexao(situacao);
      await conexao.lerPlanos();
    } else {
      await api.desconectar();
    }
  } catch {
    // servidor fora do ar: a tela de conexão mostra o erro ao tentar conectar
  }
}

iniciar();
