const ATRASO_MS = 350;
const MARGEM = 8;

export class Dicas {
  constructor() {
    this.balao = document.createElement('div');
    this.balao.className = 'dica';
    this.balao.id = 'dica';
    this.balao.setAttribute('role', 'tooltip');
    this.balao.hidden = true;
    document.body.append(this.balao);
    this.alvo = null;
    this.timer = null;

    document.addEventListener('pointerover', (e) => {
      if (e.pointerType === 'touch') return;
      const alvo = e.target.closest('[data-dica]');
      if (alvo === this.alvo) return;
      clearTimeout(this.timer);
      if (!alvo) { this.esconder(); return; }
      this.timer = setTimeout(() => this.mostrar(alvo), this.balao.hidden ? ATRASO_MS : 0);
    });
    document.addEventListener('focusin', (e) => {
      const alvo = e.target.closest('[data-dica]');
      if (alvo && e.target.matches(':focus-visible')) this.mostrar(alvo);
    });
    document.addEventListener('focusout', () => this.esconder());
    document.addEventListener('click', (e) => {
      const info = e.target.closest('.info[data-dica]');
      if (info) {
        e.preventDefault();
        if (this.alvo === info && !this.balao.hidden) this.esconder(); else this.mostrar(info);
      } else if (!e.target.closest('[data-dica]')) {
        this.esconder();
      }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') this.esconder(); });
    window.addEventListener('scroll', () => this.esconder(), true);
    window.addEventListener('resize', () => this.esconder());
  }

  mostrar(alvo) {
    const texto = alvo.dataset.dica;
    if (!texto || !alvo.isConnected) return;
    clearTimeout(this.timer);
    this.alvo?.removeAttribute('aria-describedby');
    this.alvo = alvo;
    alvo.setAttribute('aria-describedby', this.balao.id);
    this.balao.textContent = texto;
    this.balao.hidden = false;
    this.#posicionar();
  }

  esconder() {
    clearTimeout(this.timer);
    this.alvo?.removeAttribute('aria-describedby');
    this.alvo = null;
    this.balao.hidden = true;
  }

  #posicionar() {
    const r = this.alvo.getBoundingClientRect();
    const b = this.balao.getBoundingClientRect();
    const acima = r.top - b.height - MARGEM >= MARGEM;
    const topo = acima ? r.top - b.height - MARGEM : r.bottom + MARGEM;
    const esquerda = Math.min(Math.max(MARGEM, r.left + r.width / 2 - b.width / 2), window.innerWidth - b.width - MARGEM);
    this.balao.style.top = `${topo}px`;
    this.balao.style.left = `${esquerda}px`;
  }
}
