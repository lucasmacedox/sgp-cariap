// Utilitários de DOM e formatação usados por todas as telas.

export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
export const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

const ENTIDADES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (valor) => String(valor ?? '').replace(/[&<>"']/g, (c) => ENTIDADES[c]);

/** Converte "R$ 1.234,56", "119,99" ou 119.99 em número; inválido vira 0. */
export function numero(valor) {
  if (typeof valor === 'number') return valor;
  let texto = String(valor ?? '').replace(/[^\d,.]/g, '');
  if (texto.includes(',')) texto = texto.replace(/\./g, '').replace(',', '.');
  const n = parseFloat(texto);
  return Number.isFinite(n) ? n : 0;
}

/** Campo numérico opcional: texto vazio continua vazio. */
export const numeroOuVazio = (texto) => (String(texto).trim() === '' ? '' : numero(texto));

/** Valor numérico exibido num input brasileiro ("19,5"). */
export const paraCampo = (valor) => (valor === '' || valor == null ? '' : String(valor).replace('.', ','));

export const moeda = (valor) => numero(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
export const percentual = (valor) => `${numero(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

export function preencherLista(id, itens) {
  const lista = document.getElementById(id);
  if (lista) lista.innerHTML = (itens || []).map((t) => `<option value="${esc(t)}"></option>`).join('');
}

export function adiar(funcao, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => funcao(...args), ms);
  };
}

/** Acesso ao localStorage que nunca lança (aba anônima, armazenamento bloqueado). */
export const armazenamento = {
  ler(chave) {
    try { return JSON.parse(localStorage.getItem(chave) || 'null'); } catch { return null; }
  },
  gravar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); return true; } catch { return false; }
  },
};

/** Mensagens rápidas no rodapé da página. */
export class Avisos {
  constructor(elemento) {
    this.elemento = elemento;
    this.timer = null;
  }

  mostrar(mensagem, { erro = false } = {}) {
    this.elemento.textContent = mensagem;
    this.elemento.className = `toast${erro ? ' erro' : ''}`;
    this.elemento.hidden = false;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.elemento.hidden = true; }, erro ? 6000 : 3000);
  }

  erro(mensagem) {
    this.mostrar(mensagem, { erro: true });
  }
}

/** Mensagem de status ao lado de um botão. */
export function status(elemento, texto, tipo = '') {
  elemento.className = `msg${tipo ? ` ${tipo}` : ''}`;
  elemento.textContent = texto;
}

/** Ícone do sprite definido em index.html (ex.: icone('copiar')). */
/**
 * Põe um botão em estado de espera (indicador girando e texto provisório) e
 * devolve a função que o restaura. Use num try/finally.
 */
export function ocupado(botao, texto) {
  const original = botao.innerHTML;
  botao.disabled = true;
  botao.classList.add('ocupado');
  botao.setAttribute('aria-busy', 'true');
  botao.textContent = texto;
  return () => {
    botao.innerHTML = original;
    botao.disabled = false;
    botao.classList.remove('ocupado');
    botao.removeAttribute('aria-busy');
  };
}

/** Segundos como "m:ss" (ou "h:mm:ss"). */
export function duracao(segundos) {
  const s = Math.max(0, Math.round(segundos));
  const [h, m, r] = [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60];
  const mmss = `${String(m).padStart(h ? 2 : 1, '0')}:${String(r).padStart(2, '0')}`;
  return h ? `${h}:${mmss}` : mmss;
}

/** "1 plano", "3 planos". */
export const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

/** Ícone ⓘ que abre uma dica (ver componentes/dica.js). */
export const info = (texto) => `<button class="info" type="button" data-dica="${esc(texto)}" aria-label="Mais informações">${icone('info')}</button>`;

export const icone = (nome) => `<svg class="ic" aria-hidden="true"><use href="#i-${nome}"/></svg>`;
