// Combobox: lista de opções que abre ao focar, filtra ao digitar e funciona pelo teclado.
//
// Aproveita os <datalist> já existentes como fonte de dados: qualquer <input list="...">
// da página (inclusive os criados depois, em tabelas e cartões) vira combobox. Quando a
// lista tem opções lidas do SGP e o valor digitado não corresponde a nenhuma, o campo é
// marcado no próprio lugar, antes de chegar à prévia.

const LIMITE_VISIVEL = 80;

export class Combobox {
  constructor() {
    this.campo = null;
    this.ativa = -1;
    this.opcoes = [];
    this.painel = document.createElement('div');
    this.painel.className = 'combo-lista';
    this.painel.setAttribute('role', 'listbox');
    this.painel.hidden = true;
    document.body.append(this.painel);

    this.#converterTodos(document);
    new MutationObserver((mudancas) => this.#observar(mudancas))
      .observe(document.body, { childList: true, subtree: true });

    document.addEventListener('focusin', (e) => {
      if (e.target.matches?.('input[list]')) this.#converter(e.target);
      if (e.target.dataset?.lista) this.abrir(e.target);
    });
    // campo que já tinha o foco: o clique também abre a lista
    document.addEventListener('click', (e) => {
      if (e.target.dataset?.lista && (this.painel.hidden || this.campo !== e.target)) this.abrir(e.target);
    });
    document.addEventListener('input', (e) => {
      if (!e.target.dataset?.lista) return;
      this.#validar(e.target);
      if (e.target !== this.campo) return;
      // valor digitado bate com uma opção: fecha para não cobrir o que vem abaixo
      if (this.#corresponde(e.target)) this.painel.hidden = true;
      else this.#desenhar();
    });
    document.addEventListener('keydown', (e) => this.#teclar(e));
    document.addEventListener('focusout', (e) => { if (e.target === this.campo) this.fechar(); });
    this.painel.addEventListener('mousedown', (e) => {
      e.preventDefault(); // mantém o foco no campo
      const item = e.target.closest('[data-valor]');
      if (item) this.#escolher(item.dataset.valor);
    });
    window.addEventListener('resize', () => this.#posicionar());
    document.addEventListener('scroll', () => this.#posicionar(), true);
  }

  // --- conversão e validação ---------------------------------------------------

  #converter(campo) {
    campo.dataset.lista = campo.getAttribute('list');
    campo.removeAttribute('list');
    campo.classList.add('combo');
    campo.setAttribute('role', 'combobox');
    campo.setAttribute('aria-autocomplete', 'list');
    campo.setAttribute('autocomplete', 'off');
    this.#validar(campo);
  }

  #converterTodos(raiz) {
    if (raiz.matches?.('input[list]')) this.#converter(raiz);
    for (const campo of raiz.querySelectorAll?.('input[list]') ?? []) this.#converter(campo);
  }

  #observar(mudancas) {
    const listasAlteradas = new Set();
    for (const mudanca of mudancas) {
      for (const no of mudanca.addedNodes) if (no.nodeType === 1) this.#converterTodos(no);
      const lista = mudanca.target.closest?.('datalist');
      if (lista) listasAlteradas.add(lista.id);
    }
    for (const id of listasAlteradas) {
      for (const campo of document.querySelectorAll(`input[data-lista="${id}"]`)) this.#validar(campo);
      if (this.campo?.dataset.lista === id) this.#desenhar();
    }
  }

  #opcoesDe(campo) {
    const lista = document.getElementById(campo.dataset.lista);
    return lista ? [...lista.options].map((o) => ({ valor: o.value, dica: o.textContent.trim() })) : [];
  }

  #corresponde(campo) {
    const valor = campo.value.trim().toLowerCase();
    return Boolean(valor) && this.#opcoesDe(campo).some((o) => o.valor.toLowerCase() === valor);
  }

  /** Marca o campo quando há opções carregadas e o valor não é nenhuma delas. */
  #validar(campo) {
    const valor = campo.value.trim().toLowerCase();
    const opcoes = this.#opcoesDe(campo);
    const fora = Boolean(valor) && opcoes.length > 0 && !opcoes.some((o) => o.valor.toLowerCase() === valor);
    campo.classList.toggle('fora-da-lista', fora);
    if (fora) {
      campo.setAttribute('aria-invalid', 'true');
      campo.title = 'Não corresponde a nenhuma opção encontrada. Escolha uma da lista.';
    } else {
      campo.removeAttribute('aria-invalid');
      campo.removeAttribute('title');
    }
  }

  // --- lista ------------------------------------------------------------------------

  abrir(campo) {
    this.campo = campo;
    this.ativa = -1;
    this.#desenhar();
  }

  fechar() {
    this.painel.hidden = true;
    this.campo?.setAttribute('aria-expanded', 'false');
    this.campo = null;
  }

  #desenhar() {
    const campo = this.campo;
    if (!campo) return;
    const termo = campo.value.trim().toLowerCase();
    const todas = this.#opcoesDe(campo);
    const exata = todas.some((o) => o.valor.toLowerCase() === termo);
    // com um valor já escolhido, mostra tudo para facilitar a troca
    this.opcoes = (exata || !termo ? todas : todas.filter((o) => `${o.valor} ${o.dica}`.toLowerCase().includes(termo)))
      .slice(0, LIMITE_VISIVEL);
    if (!todas.length) {
      this.painel.innerHTML = '<p class="combo-vazio">Sem opções ainda. Conecte ao SGP para carregar a lista.</p>';
    } else if (!this.opcoes.length) {
      this.painel.innerHTML = '<p class="combo-vazio">Nenhuma opção com esse texto.</p>';
    } else {
      this.painel.innerHTML = this.opcoes.map((o, i) => `<div class="combo-item${i === this.ativa ? ' ativo' : ''}${o.valor.toLowerCase() === termo ? ' escolhido' : ''}"
        role="option" data-valor="${o.valor.replace(/"/g, '&quot;')}">
        <span>${escapar(o.valor)}</span>${o.dica && o.dica !== o.valor ? `<small>${escapar(o.dica)}</small>` : ''}</div>`).join('');
    }
    this.painel.hidden = false;
    campo.setAttribute('aria-expanded', 'true');
    this.#posicionar();
  }

  #posicionar() {
    if (!this.campo || this.painel.hidden) return;
    const r = this.campo.getBoundingClientRect();
    const abaixo = window.innerHeight - r.bottom;
    // no celular a lista não pode passar da largura da tela
    const largura = Math.min(Math.max(r.width, 240), window.innerWidth - 16);
    this.painel.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - largura - 8))}px`;
    this.painel.style.width = `${largura}px`;
    if (abaixo < 220 && r.top > abaixo) {
      this.painel.style.top = '';
      this.painel.style.bottom = `${window.innerHeight - r.top + 4}px`;
    } else {
      this.painel.style.bottom = '';
      this.painel.style.top = `${r.bottom + 4}px`;
    }
  }

  #teclar(evento) {
    if (evento.target !== this.campo) return;
    const total = this.opcoes.length;
    if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
      evento.preventDefault();
      if (this.painel.hidden) return this.abrir(this.campo);
      this.ativa = (this.ativa + (evento.key === 'ArrowDown' ? 1 : -1) + total) % Math.max(total, 1);
      this.#desenhar();
      this.painel.querySelector('.ativo')?.scrollIntoView({ block: 'nearest' });
    } else if (evento.key === 'Enter' && !this.painel.hidden && this.ativa >= 0 && this.opcoes[this.ativa]) {
      evento.preventDefault();
      this.#escolher(this.opcoes[this.ativa].valor);
    } else if (evento.key === 'Escape') {
      this.painel.hidden = true;
    }
  }

  #escolher(valor) {
    const campo = this.campo;
    campo.value = valor;
    campo.dispatchEvent(new Event('input', { bubbles: true }));
    campo.dispatchEvent(new Event('change', { bubbles: true }));
    this.painel.hidden = true;
  }
}

const escapar = (texto) => String(texto).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
