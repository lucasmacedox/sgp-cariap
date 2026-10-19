export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
export const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

const ENTIDADES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (valor) => String(valor ?? '').replace(/[&<>"']/g, (c) => ENTIDADES[c]);

function numero(valor) {
  if (typeof valor === 'number') return valor;
  let texto = String(valor ?? '').replace(/[^\d,.]/g, '');
  if (texto.includes(',')) texto = texto.replace(/\./g, '').replace(',', '.');
  const n = parseFloat(texto);
  return Number.isFinite(n) ? n : 0;
}

export const numeroOuVazio = (texto) => (String(texto).trim() === '' ? '' : numero(texto));

export const moeda = (valor) => numero(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

export function preencherLista(id, itens) {
  document.getElementById(id).innerHTML = (itens || []).map((t) => `<option value="${esc(t)}"></option>`).join('');
}

export const alternar = (conjunto, valor, incluir) => (incluir ? conjunto.add(valor) : conjunto.delete(valor));

export const slug = (texto) => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '').toLowerCase();

export function baixar(nome, conteudo, tipo) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
  link.download = nome;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function adiar(funcao, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => funcao(...args), ms);
  };
}

// localStorage lança em aba anônima ou com armazenamento bloqueado
export const armazenamento = {
  ler(chave) {
    try { return JSON.parse(localStorage.getItem(chave) || 'null'); } catch { return null; }
  },
  gravar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); return true; } catch { return false; }
  },
};

export class Avisos {
  constructor(elemento) {
    this.elemento = elemento;
    this.timer = null;
  }

  mostrar(mensagem, erro = false) {
    this.elemento.textContent = mensagem;
    this.elemento.className = `toast${erro ? ' erro' : ''}`;
    this.elemento.hidden = false;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.elemento.hidden = true; }, erro ? 6000 : 3000);
  }

  erro(mensagem) {
    this.mostrar(mensagem, true);
  }
}

export function status(elemento, texto, tipo = '') {
  elemento.className = `msg${tipo ? ` ${tipo}` : ''}`;
  elemento.textContent = texto;
}

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

export function duracao(segundos) {
  const s = Math.max(0, Math.round(segundos));
  const [h, m, r] = [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60];
  const mmss = `${String(m).padStart(h ? 2 : 1, '0')}:${String(r).padStart(2, '0')}`;
  return h ? `${h}:${mmss}` : mmss;
}

export const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

export const info = (texto) => `<button class="info" type="button" data-dica="${esc(texto)}" aria-label="Mais informações">${icone('info')}</button>`;

export const icone = (nome) => `<svg class="ic" aria-hidden="true"><use href="#i-${nome}"/></svg>`;
