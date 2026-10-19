// Troca de etapas, estado de cada etapa no menu lateral e botões Anterior / Próximo.

import { problemasDoMapeamento } from './dominio.js';
import { Eventos } from './estado.js';
import { $, $$, plural } from './util.js';

export const ETAPAS = ['conexao', 'mapeamento', 'lote'];

export class Navegacao {
  constructor(estado) {
    this.estado = estado;
    this.anterior = $('#btn-anterior');
    this.proximo = $('#btn-proximo');
    for (const link of $$('#passos a')) {
      link.addEventListener('click', (evento) => {
        evento.preventDefault();
        this.mostrar(link.dataset.secao);
      });
    }
    this.anterior.addEventListener('click', () => this.mostrar(ETAPAS[this.#indice() - 1]));
    this.proximo.addEventListener('click', () => this.mostrar(ETAPAS[this.#indice() + 1]));
    document.addEventListener('click', (evento) => {
      const botao = evento.target.closest('[data-ir]');
      if (botao) this.mostrar(botao.dataset.ir);
    });
    window.addEventListener('hashchange', () => this.mostrar(location.hash.slice(1)));
    for (const evento of [Eventos.ALTERADA, Eventos.RECARREGADA, Eventos.CATALOGO, Eventos.PLANOS]) {
      estado.addEventListener(evento, () => this.atualizarContadores());
    }
  }

  get atual() {
    return $$('main section').find((s) => !s.hidden)?.dataset.secao ?? 'conexao';
  }

  #indice() {
    return ETAPAS.indexOf(this.atual);
  }

  mostrar(etapa) {
    const destino = ETAPAS.includes(etapa) ? etapa : 'conexao';
    for (const secao of $$('main section')) secao.hidden = secao.dataset.secao !== destino;
    for (const link of $$('#passos a')) {
      const ativo = link.dataset.secao === destino;
      link.classList.toggle('ativo', ativo);
      if (ativo) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    }
    if (location.hash !== `#${destino}`) history.replaceState(null, '', `#${destino}`);
    this.#atualizarRodape(ETAPAS.indexOf(destino));
    window.scrollTo({ top: 0 });
  }

  #atualizarRodape(indice) {
    const nome = (i) => $(`#passos a[data-secao="${ETAPAS[i]}"] span`)?.textContent ?? '';
    this.anterior.hidden = indice <= 0;
    this.proximo.hidden = indice >= ETAPAS.length - 1;
    $('span', this.anterior).textContent = indice > 0 ? nome(indice - 1) : '';
    $('span', this.proximo).textContent = indice < ETAPAS.length - 1 ? nome(indice + 1) : '';
  }

  atualizarContadores() {
    const { config } = this.estado;
    const planos = config.grupos.reduce((total, g) => total + g.planos.length, 0);
    const problemas = problemasDoMapeamento(config).length;
    this.#marcar('conexao', '', '', this.estado.conectado);
    this.#marcar('mapeamento', problemas ? plural(problemas, 'pendência', 'pendências') : planos ? plural(planos, 'plano', 'planos') : '',
      problemas ? 'erro' : '', planos > 0 && !problemas);
    this.#marcar('lote', '', '', false);
    const vazio = $('[data-vazio="grupos"]');
    if (vazio) vazio.hidden = config.grupos.length > 0;
  }

  #marcar(etapa, texto, classe, feita) {
    const marcador = $(`[data-cont="${etapa}"]`);
    marcador.textContent = texto;
    marcador.className = texto ? classe : '';
    marcador.closest('a').classList.toggle('feito', feita);
  }
}
