// Estado da aplicação: perfis de provedor, conexão atual e última prévia.
//
// As telas não conversam entre si; alteram o estado e reagem aos eventos:
//   alterada    a configuração do provedor atual mudou (edição)
//   recarregada a configuração foi trocada inteira (outro provedor, importação)
//   catalogo    conectou, desconectou ou releu o SGP
//   provedores  a lista de provedores mudou
//   planos      os planos do SGP foram lidos ou descartados

import { normalizarConfiguracao, novaConfiguracao } from './dominio.js';
import { adiar, armazenamento } from './util.js';

const CHAVE_PERFIS = 'sgpcariap.perfis.v1';
const CHAVE_ANTIGA = 'sgpcariap.config.v1';
const PROVEDOR_INICIAL = 'Meu provedor';

export const Eventos = Object.freeze({
  ALTERADA: 'alterada',
  RECARREGADA: 'recarregada',
  CATALOGO: 'catalogo',
  PROVEDORES: 'provedores',
  PLANOS: 'planos',
});

export class Estado extends EventTarget {
  #perfis;
  #gravarAdiado = adiar(() => armazenamento.gravar(CHAVE_PERFIS, this.#perfis), 250);

  /** Conexão atual: { url, usuario, catalogo } ou null. */
  conexao = null;
  /** Planos lidos do SGP conectado: { planos_internet, planos_servico }. */
  planos = null;

  constructor() {
    super();
    this.#perfis = Estado.#carregar();
    // a gravação é adiada para agrupar edições; ao fechar ou recarregar a página, grava na hora
    window.addEventListener('pagehide', () => armazenamento.gravar(CHAVE_PERFIS, this.#perfis));
  }

  static #carregar() {
    const salvo = armazenamento.ler(CHAVE_PERFIS);
    if (salvo?.perfis && Object.keys(salvo.perfis).length) {
      for (const nome of Object.keys(salvo.perfis)) salvo.perfis[nome] = normalizarConfiguracao(salvo.perfis[nome], nome);
      if (!salvo.perfis[salvo.atual]) salvo.atual = Object.keys(salvo.perfis)[0];
      return salvo;
    }
    const antigo = armazenamento.ler(CHAVE_ANTIGA);
    const config = antigo?.versao === 1 ? normalizarConfiguracao(antigo, PROVEDOR_INICIAL) : novaConfiguracao(PROVEDOR_INICIAL);
    return { atual: PROVEDOR_INICIAL, perfis: { [PROVEDOR_INICIAL]: config } };
  }

  get config() { return this.#perfis.perfis[this.#perfis.atual]; }
  get provedor() { return this.#perfis.atual; }
  get provedores() { return Object.keys(this.#perfis.perfis).sort((a, b) => a.localeCompare(b, 'pt-BR')); }
  get conectado() { return Boolean(this.conexao); }

  existeProvedor(nome) { return Boolean(this.#perfis.perfis[nome]); }

  #emitir(evento) { this.dispatchEvent(new Event(evento)); }

  /** Avisa as telas que dependem de uma parte específica da configuração. */
  notificar(evento) { this.#emitir(evento); }

  /** Registra uma edição na configuração atual. */
  alterar() {
    this.#gravarAdiado();
    this.#emitir(Eventos.ALTERADA);
  }

  substituir(dados) {
    this.#perfis.perfis[this.provedor] = normalizarConfiguracao(dados, this.provedor);
    this.alterar();
    this.#emitir(Eventos.RECARREGADA);
  }

  definirConexao(conexao) {
    this.conexao = conexao;
    this.#emitir(Eventos.CATALOGO);
    if (!conexao) this.definirPlanos(null);
  }

  definirPlanos(planos) {
    this.planos = planos;
    this.#emitir(Eventos.PLANOS);
  }

  trocarProvedor(nome) {
    if (!this.existeProvedor(nome)) return;
    this.#perfis.atual = nome;
    armazenamento.gravar(CHAVE_PERFIS, this.#perfis);
    this.#emitir(Eventos.PROVEDORES);
    this.#emitir(Eventos.RECARREGADA);
  }

  criarProvedor(nome, config = novaConfiguracao(nome)) {
    this.#perfis.perfis[nome] = normalizarConfiguracao(config, nome);
    this.trocarProvedor(nome);
  }

  renomearProvedor(novoNome) {
    const config = this.config;
    delete this.#perfis.perfis[this.provedor];
    config.provedor = novoNome;
    this.#perfis.perfis[novoNome] = config;
    this.#perfis.atual = novoNome;
    armazenamento.gravar(CHAVE_PERFIS, this.#perfis);
    this.#emitir(Eventos.PROVEDORES);
  }

  /** Exclui o provedor atual; devolve false se for o único. */
  excluirProvedor() {
    if (this.provedores.length === 1) return false;
    delete this.#perfis.perfis[this.provedor];
    this.trocarProvedor(this.provedores[0]);
    return true;
  }
}
